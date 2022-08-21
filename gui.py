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
from binaryninjaui import UIContext
import time


def selected() -> str:
    ctx = UIContext.activeContext()
    h = ctx.contentActionHandler()
    a = h.actionContext()
    return str(a.token.token)

def peek_at(messages, delay_s=1.0) -> None:
    """Quickly display a short list of strings in status bar."""
    ProgressBarTask(messages, delay_s=delay_s).start()

class ProgressBarTask(bn.BackgroundTaskThread):
    def __init__(self, messages, delay_s):
        bn.BackgroundTaskThread.__init__(self, '', can_cancel=True)
        self.messages = messages
        self.delay_s = delay_s

    def run(self):
        messages = self.messages or ["No results to show."]
        for i, message in enumerate(messages):
            self.progress = f'DROOG ({i+1}/{len(self.messages)}) {message}'
            scaled_delay = self.delay_s * len(message) / 10
            for _ in range(int(scaled_delay / 0.1)):
                if self.cancelled:
                    break
                time.sleep(0.1)
        self.finish()