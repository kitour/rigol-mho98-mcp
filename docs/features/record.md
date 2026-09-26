# MHO98 waveform recording and replay

get_recording, set_recording, and recording_action cover the 24 documented
:RECord entries. The root server registers these tools.

    set_recording(
        session, enabled=True, frames=300, record_interval_s=0.01, prompt=False,
        start_frame=1, end_frame=300, replay_interval_s=0.1,
        mode="SING", direction="FORW",
    )
    recording_action(session, action="record_start")
    recording_action(session, action="record_stop")
    recording_action(session, action="replay_start")
    recording_action(session, action="replay_stop")

The flat readback schema is enabled, record_operate, frames,
recording_max_frames, record_interval_s, prompt, current_frame,
current_time, start_frame, end_frame, replay_max_frames, replay_interval_s,
mode, direction, and replay_operate. When replay_max_frames is zero, the
four current/start/end fields are None and their invalid frame queries are not
issued.

set_recording preserves omitted fields and validates the effective final frame
values against the current replay maximum, including start_frame <= end_frame,
before the first write. Recording intervals are 10 ns–1 s; replay intervals
are 1 ms–1 s. It never starts/stops record or replay, changes acquisition
RUN/STOP, or enables channels. mode is REP/SING; direction is FORW/BACK.

recording_action accepts record_start, record_stop, replay_start, replay_stop,
next, back, maxframes, play_first, and play_end. Starts require recording
enabled and the other operation stopped; replay and manual actions also
require recorded frames. Each result includes the canonical command, actual
readback, and an effect description.

The legacy entries :RECord:ENABle, :RECord:STARt, :RECord:FRAMes,
:RECord:CURRent, and :RECord:PLAY map to the same canonical fields/actions.
No legacy alias is transmitted. The guide prints recording maximum as
:RECord:WRECord: FMAX? with an embedded space; this module uses the
unambiguous executable :RECord:WRECord:FMAX? and treats the printed form as
a formatting erratum, not a separate command.
