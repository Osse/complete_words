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

help_args = "[reverse]"

help_args_desc="""reverse: Reverse the direction of the completion cycle

Description:

This script tries to complete the current word by looking at the last lines of
the current buffer. It is inspired by Vim's keyword completion. It does not
bind any keys by default, but it's not useful unless bindings exist. To make it
similar to Vim I suggest bind ctrl-P to "/complete_word" and ctrl-N to
"/complete_word reverse"

If someone (including you) has written 'internationalization' in the current
buffer recently you can type 'inter<ctrl-P>' and the full word will be inserted
for you. If someone had written 'internet' in the mean time that will be
inserted instead since it appeared more recently: repeat the ctrl-P keystroke
to cycle matches. If you go too far you can press ctrl-N to reverse the
direction of the cycle. If there are no matches nothing happens.

As the matches are inserted directly into the input bar there is no need to
press a key to "accept" the current completion. Just continue typing; the
script will then regard its job as done.

The default number of lines to search in is 50. If the script appears to be
slow you can reduce the number of lines to search for matches by changing the
"lines_limit". Conversely, if it rarely completes the word you want you can
increase the number.

It only considers lines that are messages written by humans (or bots). Set
"raw_lines_limit" to set an absolute limit (default 150).

By default the script uses the regex  \b\w+  to find the partial word in the
input bar and then finds candidates by searching for the partial word followed
by  \w+  . This can be customized using the "word_definition" and "word_start"
variables.

For convenience if the input bar is empty, and hence completion is meaningless,
this script performs another command instead. Set these with the "empty_cmd"
and "empty_cmd_rev" settings. By default they are set to ctrl-P and ctrl-N's
defaults respectively."""

import weechat as w
import re
from collections import OrderedDict

SCRIPT_NAME    = "complete_words"
SCRIPT_AUTHOR  = "Øystein Walle <oystwa@gmail.com>"
SCRIPT_VERSION = "0.1"
SCRIPT_LICENSE = "GPL"
SCRIPT_DESC    = "Complete words from current buffer"

settings = {
    "word_definition" : r'\w+',       # Regex used to find rest of word
    "word_start"      : r'\b\w+',     # Regex used to grab partial word
    "lines"           : '50',         # Number of lines to look in
    "raw_lines"       : '150',        # Number of lines to look in
    "empty_cmd"       : '/buffer -1', # Command to run if input bar is empty
    "empty_cmd_rev"   : '/buffer +1', # Command to run if input bar is empty
}

new_completion = True
last_lines = []
matches = []
index = 0
hooks = ('', '')

def grab_current_word(buffer):
    input_line = w.buffer_get_string(buffer, 'input')
    input_pos = w.buffer_get_integer(buffer, 'input_pos')
    left = input_line[0:input_pos+1]
    word_start = w.config_get_plugin("word_start")
    partial = re.search(word_start + '$', left, re.UNICODE)
    if partial:
        return partial.group(0)
    return None

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
             w.hook_signal("*_switch", "finish_hook", ""))

def find_matches(partial):
    word_definition = w.config_get_plugin("word_definition")
    pat = r'(?<=\b' + partial + ')' + word_definition
    global matches
    for line in last_lines:
        m = re.findall(pat, line, re.UNICODE)
        m.reverse()
        matches = matches + m
    matches = list(OrderedDict.fromkeys(matches))

def fill_last_lines(buffer):
    hdata = w.hdata_get("buffer")
    lines = w.hdata_pointer(hdata, buffer, "own_lines")

    found = 0
    processed = 0
    lines_limit = int(w.config_get_plugin("lines"))
    raw_lines_limit = int(w.config_get_plugin("raw_lines"))
    line  = w.hdata_pointer(w.hdata_get('lines'), lines, "last_line")

    while found < lines_limit and processed < raw_lines_limit and line != "":
        line_data = w.hdata_pointer(w.hdata_get('line'), line, "data")
        tag = w.hdata_string(w.hdata_get('line_data'), line_data, "0|tags_array")
        if tag == 'irc_privmsg':
            message = w.hdata_string(w.hdata_get('line_data'), line_data, "message")
            last_lines.append(message)
            found += 1
        line = w.hdata_pointer(w.hdata_get('line'), line, "prev_line")
        processed += 1

def input_bar_is_empty(buffer):
    return (w.buffer_get_string(buffer, 'input') == "")

def run_other_command(backward):
    if backward:
        w.command("", w.config_get_plugin("empty_cmd"))
    else:
        w.command("", w.config_get_plugin("empty_cmd_rev"))

# Called when invoking /complete_word
def main_hook(data, buffer, args):
    if args != "reverse":
        backward = True
    else:
        backward = False

    if input_bar_is_empty(buffer):
        run_other_command(backward)
        return w.WEECHAT_RC_OK

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
    partial = grab_current_word(buffer)
    if not partial:
        finish_completion()
        return
    find_matches(partial)
    if len(matches):
        global index
        if backward:
            index = 0
        else:
            index = len(matches) - 1
        insert_word(buffer, matches[index], '')
    else:
        finish_completion()

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
        w.hook_command("complete_word", SCRIPT_DESC, help_args, help_args_desc, "", "main_hook", "")
        # Now we wait
