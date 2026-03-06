# SENTINEL
Local LLM powered Better jarvis

PROJECT GOAL
Build a simple local AI assistant that can:
• Talk to LM Studio (Qwen model)
• Execute system commands
• Route questions to AI
• Run in a terminal loop

STACK
LM Studio (AI brain)
Python or Node.js backend
Terminal interface (CLI)

---

DAY 0 – PREP

[X] Qwen model downloaded
[X] LM Studio Local Server enabled
[X] Confirm API running at:

http://localhost:1234

[X] Create project folder

jarvis-ai/

[X] Inside folder create files:

main.py
ai.py
commands.py
config.py
logs.txt

---

DAY 1 – CONNECT TO AI

GOAL: Send a prompt to LM Studio and receive a response.

[X] Start LM Studio local server

LM Studio → Developer → Start Local Server

[X] Open terminal in project folder

[X] Implement API request to LM Studio

Endpoint example:

http://localhost:1234/v1/chat/completions

[X] Create function:

ask_ai(prompt)

Responsibilities:
• send prompt to LM Studio
• receive response
• return AI message

[X] Test with prompt:

Hello who are you

Expected:

AI prints response in terminal.

[X] Make simple CLI test

User input → send to AI → print response.

---

DAY 2 – COMMAND ROUTER

GOAL: Assistant can execute PC commands.

[ ] Create command handler function:

handle_command(text)

[ ] Detect commands using if statements or dictionary mapping.

Example commands to support:

open chrome
open vscode
open godot
open explorer

[ ] Implement system command execution.

Concept:

run_program(path)

[ ] Find paths to programs on your PC.

Examples:

Chrome.exe
Code.exe
Godot.exe

[ ] Implement logic:

IF input matches command
→ run system command

ELSE
→ send to AI

Program flow:

User input
→ command router
→ system command OR AI

---

DAY 3 – TURN IT INTO AN ASSISTANT

GOAL: Make it interactive and usable.

[ ] Add infinite input loop

while True:
get user input

[ ] Add wake word:

jarvis

Example commands:

jarvis open chrome
jarvis open vscode
jarvis what is a black hole

[ ] Parse command after wake word.

Example:

input = "jarvis open chrome"

remove "jarvis"
send rest to command router

[ ] Add help command.

jarvis help

Output example:

Available commands:
open chrome
open vscode
open godot
open explorer

[ ] Add exit command.

jarvis exit

Program stops.

[ ] Add logging.

Save every command to:

logs.txt

---

OPTIONAL FEATURES (IF YOU FINISH EARLY)

[ ] System info command

jarvis cpu
jarvis ram

[ ] File search

jarvis find filename

[ ] AI coding helper

jarvis explain this code

[ ] Add command history

---

PROJECT STRUCTURE

jarvis-ai/

main.py
Program loop and input handling

ai.py
LM Studio communication

commands.py
System commands

config.py
Settings and paths

logs.txt
Command history

---

VERSION 1 COMPLETE WHEN:

[ ] AI responses work
[ ] System commands launch apps
[ ] Commands routed correctly
[ ] Wake word works
[ ] Assistant runs continuously

At this point you have a working local AI assistant.
