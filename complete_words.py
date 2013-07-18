# -*- coding: utf-8 -*-
#
# Copyright (c) 2013 Øystein Walle <oystwa@gmail.com>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import weechat as w
import re

SCRIPT_NAME    = "complete_words"
SCRIPT_AUTHOR  = "Øystein Walle <oystwa@gmail.com>"
SCRIPT_VERSION = "00000000001"
SCRIPT_LICENSE = "GPL"
SCRIPT_DESC    = "Complete words from current buffer"

settings = {
    "word_definition" : r'\b\w+\b',        # Regex used to match words
    "lines"           : '50',              # Number of lines to look in
    "key_backward"    : 'ctrl-T',          # Key to complete backwards
    "key_forward"     : 'ctrl-N',          # Key to complete forwards
}

prev_completion = { 'done': True }
last_lines = []
matches = []
index = 0
input_hook = "foo"

def debug_stuff(vars):
    for k, v in vars.items():
        w.prnt("", k + ': ' + str(v))

def grab_current_word(buffer):
    input_line = w.buffer_get_string(buffer, 'input')
    input_pos = w.buffer_get_integer(buffer, 'input_pos')
    left = input_line[0:input_pos+1]
    part = re.search(r'\b\w+$', left, re.UNICODE)
    if part:
        return part.group(0)
    return part

def insert_word(buffer, index):
    rollover = 0
    if index >= len(matches):
        rollover = 1
    index = index % len(matches)
    string = matches[index]
    input_line = w.buffer_get_string(buffer, 'input')
    input_pos = w.buffer_get_integer(buffer, 'input_pos')

    if index == 0 and rollover == 1:
        prev_len = len(matches[-1])
    elif index > 0:
        prev_len = len(matches[index-1])
    else:
       prev_len = 0
    left = input_line[0:input_pos - prev_len]
    new_pos = input_pos + len(string) - prev_len

    right = input_line[input_pos:]
    result = left + string + right

    # If we don't deactivate the hook temporarily it is triggered
    global input_hook
    if input_hook: w.unhook(input_hook)
    w.buffer_set(buffer, 'input', result)
    w.buffer_set(buffer, 'input_pos', str(new_pos))
    input_hook = w.hook_signal("input_text_*", "finish_completion", "")

def find_matches(part):
    pat = r'(?<=\b' + part + r')\w+'
    for line in last_lines:
        m = re.findall(pat, line)
        m.reverse()
        global matches
        matches = matches + m

def fill_last_lines(buffer):
    hdata = w.hdata_get("buffer")
    lines = w.hdata_pointer(hdata, buffer, "own_lines")
    line  = w.hdata_pointer(w.hdata_get('lines'), lines, "last_line")

    i = 0
    search_limit = int(w.config_get_plugin("lines"))
    while i < search_limit and line != "":
        line_data = w.hdata_pointer(w.hdata_get('line'), line, "data")
        message = w.hdata_string(w.hdata_get('line_data'), line_data, "message")
        last_lines.append(message)
        line = w.hdata_pointer(w.hdata_get('line'), line, "prev_line")
        i = i + 1

# Called when pressing Ctrl-T. Starts or continues completion
def main_hook(data, buffer, args):
    if prev_completion['done'] == False:
        continue_completion(buffer)
    else:
        complete_word(buffer)
    return w.WEECHAT_RC_OK

def complete_word(buffer):
    # Set flag
    global prev_completion
    prev_completion['done'] = False

    fill_last_lines(buffer)
    part = grab_current_word(buffer)
    if part:
        find_matches(part)
    else:
        finish_completion(None, None, None)
        return
    if len(matches):
        insert_word(buffer, 0)
    else:
        finish_completion(None, None, None)
        w.prnt("", "No matches")

def continue_completion(buffer):
    global index
    index = index + 1
    # Just insert the next word from matches
    # insert_word() takes care of removing the old one
    insert_word(buffer, index)

# Called when the cursor is moved after attempting completion
# Taken as a signal that the completion is done
def finish_completion(signal, type_data, signal_data):
    global prev_completion
    prev_completion['done'] = True
    global last_lines
    last_lines = []
    global matches
    matches = []
    global index
    index = 0
    w.unhook(input_hook)

if __name__ == "__main__":
    if w.register(SCRIPT_NAME, SCRIPT_AUTHOR, SCRIPT_VERSION, SCRIPT_LICENSE,
                  SCRIPT_DESC, "", ""):
        # Set default settings
        for option, default_value in list(settings.items()):
            if not w.config_is_set_plugin(option):
                w.config_set_plugin(option, default_value)
        w.hook_command("complete_word", "", "", "", "", "main_hook", "")
        # Now we wait
