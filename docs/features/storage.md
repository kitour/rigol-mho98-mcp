# MHO98 instrument save/load

The storage tools control non-image files on the oscilloscope. They do not
read or write the Mac filesystem. Instrument paths use `C:/` for local
instrument storage and `D:/` for USB storage; the guide also documents `E:/`
as a mask-load location. Host transfers remain separate: use
`download_binary`, `restore_setup`, or waveform export tools for files on the
host. SMB configuration, credentials, remote shares, directory listing, and
arbitrary upload are unsupported.

## Tools and schema

`get_storage {}` returns:

```json
{
  "pathname": "C:/",
  "prefix": "Rigol",
  "overwrite": false,
  "status": "complete",
  "status_code": 1
}
```

The returned `pathname` and `prefix` are native instrument readback values
(after surrounding whitespace is removed). Firmware may return a native path
outside the accepted setter syntax, such as `/data/UserData`; it is returned
as-is, never treated as a host path, and never translated to `C:/`. Readback
does not apply the outgoing input restrictions.

`set_storage({pathname?, prefix?, overwrite?})` changes only supplied settings
and returns the same readback. Its optional `pathname` input is an instrument
directory accepted by the setter (`C:/` or `D:/`); it is not a host path.
Its optional `prefix` input is an ASCII filename prefix without a suffix and is
limited to 16 characters. These write-input restrictions do not constrain the
native values returned by `get_storage`.
`overwrite` controls `:SAVE:OVERlap`; it is never enabled implicitly.

`save_file({kind, path, overwrite?})` supports:

| `kind` | command | suffixes |
| --- | --- | --- |
| `setup` | `:SAVE:SETup` | `.stp` |
| `waveform` | `:SAVE:WAVeform` | `.bin`, `.csv` |
| `memory_waveform` | `:SAVE:MEMory:WAVeform` | `.bin`, `.csv`, `.wfm` |
| `mask` | `:SAVE:MASK` | `.pf` |

The final filename is limited to 26 ASCII characters. Supported path
components contain only ASCII letters, numbers, `_`, `-`, and `.`; absolute
host paths, backslashes, `.`/`..`, control characters, and other injection-prone
characters are rejected before a write. `overwrite` may be `true` or `false`
to make an explicit policy choice. If omitted, the current instrument policy
is queried and preserved, including an already-enabled policy; the tool never
silently turns overlap on.

The result includes `status_code` from the immediate `:SAVE:STATus?` query and
`status`, either `complete` (`1`) or `pending` (`0`). `pending` is not reported
as completed, and this feature does not poll indefinitely or add a timing
limit. A memory-waveform save additionally requires existing trigger status
`STOP` and validates `:ACQuire:MDEPth?` as `AUTO` or an integer from 1 through
500,000,000. The scope is not stopped automatically.

`load_file({kind, path})` supports only `setup` (`:LOAD:SETup`, `.stp`) and
`mask` (`:LOAD:MASK`, `.pf`). Loading intentionally replaces the corresponding
instrument setup or mask. It does not perform an automatic full reset, upload
a host file, or provide a completion status because the guide documents no
load-status query.

## Destructive effects and limits

Saving with overlap enabled can replace an existing instrument file. Loading
replaces the selected setup or mask. These tools do not list directories or
preflight file existence because no documented directory-listing command is
used; callers must choose the overlap policy explicitly or inspect the returned
policy. Image save/data commands are intentionally out of scope.
