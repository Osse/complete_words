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
#

# Complete words Vim-style
# ------------------------
#
# This script defines a command /complete that tries to complete the current
# word by looking at the last lines of the current buffer (50 by default). It
# is inspired by Vim's keyword completion.
#
# This script does not bind any keys by default, but due to its nature it is
# not useful unless bindings exist. The author suggests:
#
# /bind key ctrl-P /complete
# /bind key ctrl-N /complete reverse
#
# If someone (including you) has written e.g. 'internationalization' in the
# current buffer recently then you can type 'inter<Ctrl-P' and
# 'internationalization' will be inserted for you. If someone had written
# 'internet' in the mean time that will be inserted instead since it appeared
# more recently. Repeat the Ctrl-P keystroke to cycle matches. If you go too
# far you can press Ctrl-N to reverse the direction of the cycle.
#
# As the matches are inserted directly into the input bar there is no need to
# press a key to "accept" the current completion. Just continue typing; the
# script will then regard its job as done.
#
# If the script appears to be slow you can reduce the number of lines to search
# for matches in:
#
# /set plugins.var.python.complete_words.lines 25
#
# Conversely, if it rarely completes the word you want you can increase the
# number.
#
# By default the script uses the regex \b\w+ to find the partial word in the
# input bar and then searches for matches to the partial word followed by \w+.
# This can be customized using the word_definition and word_start variables.

import weechat as w
import re
from collections import OrderedDict

SCRIPT_NAME    = "complete_words"
SCRIPT_AUTHOR  = "Øystein Walle <oystwa@gmail.com>"
SCRIPT_VERSION = "0.1"
SCRIPT_LICENSE = "GPL"
SCRIPT_DESC    = "Complete words from current buffer"

settings = {
    "word_definition" : r'\w+',   # Regex used to find rest of word
    "word_start"      : r'\b\w+', # Regex used to grab partial word
    "lines"           : '50',     # Number of lines to look in
}

new_completion = True
last_lines = []
matches = []
index = 0
hooks = ('', '')

def debug_stuff(vars):
    for k, v in vars.items():
        w.prnt("", k + ': ' + str(v))

def grab_current_word(buffer):
    input_line = w.buffer_get_string(buffer, 'input')
    input_pos = w.buffer_get_integer(buffer, 'input_pos')
    left = input_line[0:input_pos+1]
    word_start = w.config_get_plugin("word_start")
    part = re.search(word_start + '$', left, re.UNICODE)
    if part:
        return part.group(0)
    return part

def insert_word(buffer, word, prev_word):
    input_line = w.buffer_get_string(buffer, 'input')
    input_pos = w.buffer_get_integer(buffer, 'input_pos')

    strip_len = len(prev_word)
    left = input_line[0:input_pos - strip_len]
    new_pos = input_pos + len(word) - strip_len
    right = input_line[input_pos:]
    result = left + word + right

    # If we don't deactivate the hook temporarily it is triggered
    global hooks
    map(w.unhook, hooks)
    w.buffer_set(buffer, 'input', result)
    w.buffer_set(buffer, 'input_pos', str(new_pos))
    hooks = (w.hook_signal("input_text_*", "finish_hook", ""),
             w.hook_signal("buffer_switch", "finish_hook", ""))

def find_matches(part):
    word_definition = w.config_get_plugin("word_definition")
    pat = r'(?<=\b' + part + ')' + word_definition
    global matches
    for line in last_lines:
        m = re.findall(pat, line, re.UNICODE)
        m.reverse()
        matches = matches + m
    matches = list(OrderedDict.fromkeys(matches))

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
    if args == "backward":
        backward = True
    else:
        backward = False
    global new_completion
    if new_completion == False:
        continue_completion(buffer, backward)
    else:
        # Set flag
        new_completion = False
        complete_word(buffer, backward)
    return w.WEECHAT_RC_OK

# Called when the cursor is moved after attempting completion
# Taken as a signal that the completion is done
def finish_hook(signal, type_data, signal_data):
    finish_completion()
    return w.WEECHAT_RC_OK

def complete_word(buffer, backward):
    fill_last_lines(buffer)
    part = grab_current_word(buffer)
    if not part:
        finish_completion()
        return
    find_matches(part)
    if len(matches):
        global index
        if backward:
            index = 0
        else:
            index = len(matches) - 1
        insert_word(buffer, matches[index], '')
    else:
        finish_completion()
        w.prnt("", "No matches")

def continue_completion(buffer, backward):
    global index
    prev_word = matches[index]
    if backward:
        index = (index + 1) % len(matches)
    else:
        index = (index + len(matches) - 1) % len(matches)
    word = matches[index]
    insert_word(buffer, word, prev_word)

# Cleanup function
def finish_completion():
    global new_completion
    new_completion = True
    global last_lines
    last_lines = []
    global matches
    matches = []
    global index
    index = 0
    global hooks
    map(w.unhook, hooks)
    hooks = ('', '')

if __name__ == "__main__":
    if w.register(SCRIPT_NAME, SCRIPT_AUTHOR, SCRIPT_VERSION, SCRIPT_LICENSE,
                  SCRIPT_DESC, "", ""):
        # Set default settings
        for option, default_value in list(settings.items()):
            if not w.config_is_set_plugin(option):
                w.config_set_plugin(option, default_value)
        w.hook_command("complete_word", "", "", "", "", "main_hook", "")
        # Now we wait
