# Device control for Windows 11 and Linux Mint

Version 1.3 adds `/pc get_volume {}`, `/pc set_volume {"percent":50}` and
`/pc get_brightness {}`, plus local paraphrases such as `make display half bright`.
Absolute volume uses `pactl` on Linux and the optional `pycaw` dependency on Windows.
The [local-first guide](local-first.md) explains the capability registry, device
adapters, risk classes and unchanged confirmation boundaries.

Jarvis can operate your local desktop through individually confirmed actions.
It runs with your normal account permissions. This does not give ChatGPT remote
access to your laptop, bypass UAC, or control Android. Install/run this version
on the computer you want to control.

## Start

The desktop installers include the control dependencies. For a source checkout:

```bash
python -m pip install -r requirements-control.txt
```

On Linux Mint, use an **X11** desktop session for mouse, keyboard, windows and
media controls. Install the window/media utilities and file opener:

```bash
sudo apt install xdotool wmctrl xdg-utils x11-xserver-utils
```

Use **Device controls → Enable device control**, or type:

```text
/control on
/computer
/brightness 50
```

Jarvis displays the exact action and arguments. Nothing changes until you type
`/confirm TOKEN` using the token in that preview. Tokens are single-use, expire
after five minutes and disappear on restart, clear, stop or re-enable. Voice
can request actions; enabling control and confirming require typed input.

Device control starts **off every time**. Enabling it is session-only and does
not approve actions. Existing configured app launching still works independently
with its existing confirmation requirement.

## What you can do

| Control | Offline example | Notes |
|---|---|---|
| System status | `/computer` | CPU, RAM, free space on the home drive, battery |
| Processes | `/processes` | Up to 40 of your own processes, highest RAM first |
| Applications | `/open vscode` | Existing `JARVIS_APPS_JSON` aliases |
| Browser | `/browse https://example.com` | Opens your default browser |
| Type text | `/type Hello Hirunthakan` | Printable English keyboard text, max 500 characters |
| Shortcut | `/key ctrl+s` | One key or combination; `/key enter` is a separate action |
| Windows | `/window maximize` | Also minimize, restore, switch, close, desktop |
| Sound | `/media volume_up` | Also volume_down and mute; one keypress per action |
| Playback | `/media play_pause` | Also next and previous; requires media-key support |
| Brightness | `/brightness 50` | 10–100%; hardware/driver support required |
| Power | `/power lock` | Also sleep, restart and shutdown |
| Files | `/folder /home/YOU/Documents` | Configured roots only |
| Screenshots | GUI **Screenshot** | Existing explicit capture/share prompt; selected AI provider receives image |

Ask naturally: “Mute the volume”, “Set brightness to 50%”, “Show my running
processes” or “Lock my computer”. These phrases and all slash controls run
without an AI API key. Teach custom phrases with `/learn`, or disable general AI
with `/ai off`. See [local commands and offline voice](local-commands.md).
No tool can approve its own request.

### Pointer and detailed actions

Use `/pc TOOL {JSON arguments}` for exact actions:

```text
/pc mouse_move {"x":400,"y":300}
/pc mouse_click {"x":400,"y":300,"button":"left","clicks":2}
/pc scroll {"direction":"down","steps":3}
/pc terminate_process {"pid":1234}
```

Input affects the **primary monitor** and the focused application. After an
input confirmation, the GUI minimizes and waits four seconds. Focus the intended
app during that time; in the CLI switch from your terminal yourself. Avoid
changing focus while typing. Coordinates are pixels and must be inside the screen.
Jarvis reports that input was sent; it cannot automatically verify application
state. Keyboard layout affects the typed characters. Tamil/other Unicode text can
be saved with `write_text` below; simulated Unicode typing is not implemented.

Closing a window, terminating a process, pressing Enter, or a shortcut may discard
work, submit a form, send a message or run text in a terminal. Check the target and
preview. Process confirmation is bound to its creation time to prevent terminating
a replacement process with a reused PID. System processes, other users' processes,
Jarvis and its parent processes are rejected. On Windows, process termination can
be abrupt; save work first.

### Files

Set `JARVIS_FILE_ROOTS_JSON` in your settings and restart Jarvis:

```dotenv
# Linux
JARVIS_FILE_ROOTS_JSON=["/home/YOU/Documents","/home/YOU/Projects"]
# Windows example (use this instead of the line above)
# JARVIS_FILE_ROOTS_JSON=["C:\\Users\\YOU\\Documents"]
```

Use actual absolute paths. JSON Windows paths need doubled backslashes.

```text
/pc manage_file {"action":"create_folder","path":"/home/YOU/Documents/Study"}
/pc manage_file {"action":"write_text","path":"/home/YOU/Documents/Study/notes.txt","text":"வணக்கம்\nStudy notes"}
/pc manage_file {"action":"copy","path":"/home/YOU/Documents/Study/notes.txt","destination":"/home/YOU/Documents/Study/backup.txt"}
/pc manage_file {"action":"move","path":"/home/YOU/Documents/Study/backup.txt","destination":"/home/YOU/Documents/Study/renamed.txt"}
/pc open_path {"path":"/home/YOU/Documents/Study/notes.txt"}
/pc manage_file {"action":"trash","path":"/home/YOU/Documents/Study/renamed.txt"}
```

Each example creates a separate preview. Destination parents must exist. File
operations accept regular files up to 20 MB; new text is limited to 8,000
characters. Existing files are never overwritten. Edit existing documents in
their application using the keyboard controls, or write a new version with a new
filename. Trash uses the OS Trash/Recycle Bin, with no permanent-delete fallback.
No folder deletion, recursive copy or hidden-file access is implemented. Links,
junctions, special paths and traversal outside configured roots are rejected.
Changes to file identity/size/timestamps after a preview invalidate confirmation.
These checks are for a local user's workflow, not isolation against another
malicious process racing filesystem changes. Opening an executable file can run it.

## Stop and limitations

- **Stop / interrupt** or `/stop` disables control and clears pending approvals.
- Moving the mouse to a corner of the primary screen triggers PyAutoGUI's
  fail-safe on its next input call. Control then turns off. Move away from the
  corner before enabling again. This fail-safe applies to mouse/keyboard input;
  use Stop for file/power actions.
- Input and power actions have a four-second cancellable delay. Once an OS
  request is submitted or a short input call starts, Stop cannot undo it.
- CLI users can press **Ctrl+C** to exit and stop. Keep the GUI accessible when
  testing. Already typed text, submitted requests and completed files remain.
- No unattended desktop loop, direct arbitrary-shell tool, network control
  listener, keylogging, privilege escalation or background startup is installed.
- Linux Wayland automation, secure/login/UAC desktops and phone control are
  unsupported. Brightness, media keys, screen locking and sleep depend on your
  hardware and desktop configuration. Jarvis does not elevate itself on failure.
- Control commands are audited by action name and status, without arguments.
  Natural-language conversations/AI tool previews may contain requested text or
  file paths; do not ask Jarvis to type passwords. Screen sharing remains explicit.

## Device checks after installation

1. Start offline. Verify `/control status` is off; inspect `/computer`.
2. Enable controls, request mute, cancel it and verify volume is unchanged.
3. Repeat mute and confirm once; confirm again and verify it is rejected.
4. Open a disposable text editor. Confirm `/type Jarvis test`, focus it during
   the delay, and verify the text. Test `/key ctrl+s` only in that editor.
5. Start a longer typing action and use the mouse-corner stop; confirm control
   turns off. Re-enable and test Stop during a power/input countdown.
6. In a temporary configured folder, test create, copy, move and Trash. Try an
   existing destination and an out-of-root path; both should be rejected.
7. Test window minimize/restore, media keys and brightness on your actual laptop.
8. Save all work before separately testing lock, sleep, restart or shutdown.

Unit tests mock hardware and OS effects. Windows/Linux installer CI checks
packaging, imports, startup, installation and uninstall; it does not prove real
keyboard layout, hardware brightness, microphone, UAC or power behavior.

Implementation references: [PyAutoGUI](https://pyautogui.readthedocs.io/en/latest/),
[psutil](https://psutil.readthedocs.io/stable/),
[screen-brightness-control](https://github.com/Crozzers/screen_brightness_control),
[Send2Trash](https://github.com/arsenetar/send2trash),
[Windows shutdown](https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/shutdown).
