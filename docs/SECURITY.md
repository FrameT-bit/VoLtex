# VoLtex Security Notes

## Stored Data

VoLtex uses these storage locations:

```text
~/.local/share/voltex/webview
~/.local/state/voltex
system keyring
```

App directories are created with `0700` permissions.

## Keyring

When the web page exposes a readable `session_token`, VoLtex stores it through Python `keyring`, backed by the user's desktop secret service such as GNOME Keyring or KWallet. VoLtex does not write that token to its own plaintext config file.

## WebKit Session

GTK WebKit persists normal browser state so users do not need to log in every launch. This is required for `HttpOnly` cookies, because JavaScript cannot read them and VoLtex cannot put them in keyring itself.

## Logs

Bridge logs redact sensitive fields:

```text
authorization
cookie
password
session_token
token
```

The launcher log is written to:

```text
~/.local/state/voltex/launcher.log
```

Wine/Vortex output is written to:

```text
~/.local/state/voltex/game.log
```

VoLtex redacts token-like query parameters before writing command lines or process output to `game.log`.

## Remaining Exposure

The final game launch URI is passed to Vortex as a process argument because that is the protocol Vortex expects. Local users with process-inspection privileges may be able to see process arguments while the launch is happening. VoLtex avoids persisting that URI in logs.

The installer does not install system packages unless the user explicitly passes `--install-system-deps`.
