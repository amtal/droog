# DROOG - pDf Reference Opcodes Or reGisters
# Copyright (C) 2020  amtal
# 
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
# 
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
import pymupdf  # pip install pymupdf  (AGPLv3)
import binaryninja as bn
import os.path
from pathlib import Path
import base64
import glob
import re
from . import gui
from time import time
import atexit
import tempfile
from concurrent.futures import ThreadPoolExecutor

# Look for PDFs in architecture plugins.
#
# Wildly guesses arch plugin name through size/endianness tags.
# Has to be same install method as this one. ;)
# Hangs if you've got recursive links in plugin dirs??
STRIP_VARIANTS = r"_?(32|64)?(el|eb|be|_le|_eb|_be|l)?$"
PLUGIN_DIR = Path(__file__).parent.parent.absolute()

def find_manuals_in_siblings(arch_guess):
    return glob.glob(f"{PLUGIN_DIR}/*{arch_guess}*/**/*.pdf", recursive=True)

manuals = {}  # main cache, acceptable RAM use
def go(instr, action="Search", bv=None, arch=None):
    with ThreadPoolExecutor(max_workers=8, thread_name_prefix='DROOG') as pool:
        arch_guess = re.sub(STRIP_VARIANTS, "", arch or bv.arch.name)
        global manuals
        if arch_guess not in manuals:
            t = time()
            # check expensive glob only on startup, deletions require a restart anyway
            own_manuals = os.path.join(os.path.dirname(__file__), 'manuals', arch_guess, '*.pdf')
            manuals[arch_guess] = {pdf:Manual(pdf) for pdf in glob.glob(own_manuals) + 
                                                              find_manuals_in_siblings(arch_guess)}
            bn.log_info(f"Loaded {len(manuals[arch_guess])} manuals for {arch_guess} in {time()-t:.2f}s", "Plugin.DROOG")

        t = time()
        futures = [pool.submit(manuals[arch_guess][pdf].go, instr, action, pool, bv) 
                    for pdf in manuals[arch_guess]]
        for f in futures:  # imagine there's no global GIL lock, it's easy if you try
            f.result()     # in python 4.15, no hell below us, above us only sky
        bn.log_info(f"Searched and rendered {instr} in {time()-t:.2f}s", "Plugin.DROOG")

TOKENIZE = r'[ —]+'  # space in general, em-dash for Intel

class Manual:
    def __init__(self, pdf):
        self.doc = pymupdf.open(pdf)
        self.toc = self.doc.get_toc(simple=True)
        self.filename = os.path.basename(pdf)
        self.filepath = pdf

    def go(self, instr: str, action='Peek', pool=None, bv=None):
        t = time()

        match_type = bn.Settings().get_string("droog.tokenFilter", bv)
        if match_type == "Convert to Upper":
            instr = instr.upper()

        if match_type == "Case Insensitive":
            matches = [(i,(lvl,title,page)) for i,(lvl,title,page) in enumerate(self.toc) 
                        if instr.lower() in re.split(TOKENIZE, str(title).lower())]
        else:
            matches = [(i,(lvl,title,page)) for i,(lvl,title,page) in enumerate(self.toc) 
                        if instr in re.split(TOKENIZE, str(title))]
        bn.log_info(f"Found {len(matches)} matches in {self.filename} in {time()-t:.2f}s", "Plugin.DROOG")


        if action == 'Peek':
            msgs = [f'   "{title}"   {self.filename}:{page}' for _,(_,title,page) in matches]
            gui.peek_at(msgs, bn.Settings().get_double("droog.statusbarPeekSpeed", bv))
        elif action == 'Search':
            zoom = bn.Settings().get_double("droog.pdfRenderZoom", bv)

            reports = bn.interaction.ReportCollection()
            for toc_index, (_page_lvl, page_title, page_no) in matches:
                # assuming ToC is sequential, get all pages until next heading
                # it should probably be same-level heading in case there's sub-headings
                # in the section we found, but whatever... open PDF in browser if you care
                start_page = page_no - 1
                if toc_index + 1 < len(self.toc):
                    end_page = self.toc[toc_index + 1][2] # page_no
                else:
                    end_page = start_page

                pages = list(self.doc.pages(start_page, end_page+1, 1)) 
                # URI to file:// strips the #page part unless we pass it via
                # a redirect-stub file, or HTTP host ./manuals/ lol
                html = f'<b>{self.doc.metadata.get("title", "")}</b><br>'
                futures = [pool.submit(render_page, p, zoom) for p in pages]
                html += ''.join([f'<a href={create_redirect_html(self.filepath, p.number + 1)}>{t}</a>' 
                                 for t,p in zip([f.result() for f in futures], pages)])
                reports.append(bn.HTMLReport(page_title, html))
            if len(reports):
                bn.execute_on_main_thread(lambda: bn.show_report_collection(f'{instr} in {self.filename}', reports))
            else:
                gui.peek_at([])
        elif action == 'Open':
            import webbrowser
            assert len(matches) < 10, f'way too many matches for browser: {matches}'
            for _, (_, _, page_no) in matches:
                # used to be #args would get stripped and you needed a redirect stub
                # but this should work on most architectures now?
                webbrowser.open(f"file://{self.filepath}#page={page_no}")

# Mandatory Carmackian Latency Analysis
#
#   All the outputs are non-interactive, so at least we can unblock the UI.
# Time from query to modal popups is what sucks, though. There's no streaming
# or lazy output with the report API, so parallelism's the only option but
# that means multiprocessing or waiting 'til GIL-less Python. Search is fast
# as long as cache's already built, so getting that out of the way is first
# prio.
#   PDF viewer startup will always be slow. In-Binja "View" is the main thing
# that feels bad.
#   We *can* cheat by following the search with an instant selection popup,
# with rendering in the background that respects the eventual response.
#
# Rendering PNG is what's really slow. But HTML view isn't remotely there.

def render_page(page, zoom=1.4):
    mat = pymupdf.Matrix(zoom, zoom) if zoom != 1.0 else None
    jpg = page.get_pixmap(matrix=mat).tobytes(output='png')
    return f'<img src="data:image/png;base64,{base64.b64encode(jpg).decode()}"/>'

# URI PDF #page Hyperlinking
# file:// inbounds different/external source get #args stripped off
# so this or something worse has to happen:

spaghetti = []  # if binja segfaults we spill it :(

def cleanup_spaghetti():
    for file_path in spaghetti:
        try:
            os.remove(file_path)
        except Exception as e:
            pass  # best effort

atexit.register(cleanup_spaghetti)

def create_redirect_html(pdf_path, page_number):
    with tempfile.NamedTemporaryFile('w', prefix="Plugin.DROOG", suffix='.html', delete=False) as temp_html:
        spaghetti.append(temp_html.name)
        file_url = f'file:///{pdf_path}#page={page_number}'
        temp_html.write(f'''
        <html><body><script>
            window.location.href="{file_url}";
        </script></body></html>''')
        temp_html.flush()
        return 'file://'+temp_html.name
