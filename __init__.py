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
import binaryninja as bn
from . import gui, index
import json

def is_valid(bv, _addr):
    return bv.arch != None

def act(bv, action):
    token = gui.selected()
    if not token:
        return
    bn.log_info(f"{action}ing {token} in {bv.arch.name}", "Plugin.DROOG")
    index.go(token, action, bv=bv)

def bg_act(bv, action):  # unblock GUI thread
    bn.worker_interactive_enqueue(lambda: act(bv, action), f"Plugin.DROOG {action}")


desc = 'these descriptions should show up in cmd-P as hints or something'
bn.PluginCommand.register_for_address('DROOG\\Peek Reference Headings', desc, 
                                        lambda bv,_: bg_act(bv, 'Peek'), is_valid)
bn.PluginCommand.register_for_address('DROOG\\Search References...', desc, 
                                        lambda bv,_: bg_act(bv, 'Search'), is_valid)


settings = bn.Settings()
assert settings.register_group("droog", "DROOG (pDf Reference Opcodes Or reGisters)")
assert settings.register_setting("droog.tokenFilter", json.dumps({
    "title": "Token Conversions",
    "type": "string",
    "default": "Case Insensitive",
    "description": "How architecture plugin symbols differ from manuals.",
    "enum": [
        "Case Insensitive",
        "Convert to Upper",
        "As Is"
    ],
    "enumDescriptions": [
        "Default option, but will false positive on common words like AND/OR.",
        "Uppercase before search (e.g. aarch64 arch matches GCC, but manuals are shouty.)",
        "As Is (e.g. Z80 plugin matches common manuals exactly.)"
    ]
}))
assert settings.register_setting("droog.statusbarPeekSpeed", json.dumps({
    "title": "Statusbar Peek Speed",
    "type": "number",
    "default": 0.5,
    "description": "Seconds per ten characters spent displaying previews in status bar."
}))
assert settings.register_setting("droog.pdfRenderZoom", json.dumps({
    "title": "PDF Page Render Zoom",
    "type": "number",
    "default": 1.4,
    "description": "Smaller or 1.0 is noticeably faster!"
}))