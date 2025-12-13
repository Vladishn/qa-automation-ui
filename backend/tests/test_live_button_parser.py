from backend.app.live_button_log_parser import parse_live_button_logs


def test_parse_live_button_logs_detects_all_phases() -> None:
    log_text = """
    12-08 11:00:00.100 I/QA_LIVE: CONFIG_START channel=50
    12-08 11:00:01.000 I/quickset: Saved StingTV channel: 50
    12-08 11:00:05.500 I/QA_LIVE: PHASE1_START expected_channel=50
    12-08 11:00:05.600 I/GlobalKeyInterceptor: onReceive keyCode = 172
    12-08 11:00:06.000 I/ActivityTaskManager: START u0 cmp=il.co.partnertv.atv/.HomeActivity pkg=il.co.partnertv.atv
    12-08 11:00:07.000 I/PartnerTV+: PartnerTV+ GUIDE intent sent with channel: 50
    12-08 11:01:00.500 I/QA_LIVE: PHASE2_START expected_channel=50
    12-08 11:01:00.600 I/GlobalKeyInterceptor: one key down 172
    12-08 11:01:01.000 I/ActivityTaskManager: ACTIVITY pkg=il.co.partnertv.atv
    12-08 11:01:02.000 I/PartnerTV+: PartnerTV+ GUIDE intent sent with channel: 50
    12-08 11:02:00.500 I/QA_LIVE: PHASE3_START expected_channel=50
    12-08 11:02:10.500 I/QA_LIVE: PHASE3_DEVICE_READY expected_channel=50
    12-08 11:02:11.000 I/GlobalKeyInterceptor: onReceive keyCode = 172
    12-08 11:02:11.200 I/ActivityTaskManager: START u0 cmp=il.co.partnertv.atv/.HomeActivity pkg=il.co.partnertv.atv
    12-08 11:02:12.000 I/PartnerTV+: PartnerTV+ GUIDE intent sent with channel: 50
    """
    signals = parse_live_button_logs(log_text, expected_channel=50)

    assert signals.config_saved_channel == 50
    assert signals.config_attempted is True
    phases = {phase.phase: phase for phase in signals.phases}
    assert phases["PHASE1"].observed_channel == 50
    assert phases["PHASE2"].observed_channel == 50
    assert phases["PHASE3"].observed_channel == 50
    assert phases["PHASE1"].live_key_pressed is True
    assert phases["PHASE2"].partnertv_launched is True
    assert phases["PHASE1"].raw_excerpt and "GUIDE intent" in phases["PHASE1"].raw_excerpt


def test_parse_live_button_logs_tracks_wrong_channel_in_phase3() -> None:
    log_text = """
    12-08 11:00:01.000 I/quickset: Saved StingTV channel: 50
    12-08 11:00:05.500 I/QA_LIVE: PHASE1_START expected_channel=50
    12-08 11:00:06.000 I/GlobalKeyInterceptor: onReceive keyCode = 172
    12-08 11:00:07.000 I/PartnerTV+: PartnerTV+ GUIDE intent sent with channel: 50
    12-08 11:02:00.500 I/QA_LIVE: PHASE3_START expected_channel=50
    12-08 11:02:10.500 I/QA_LIVE: PHASE3_DEVICE_READY expected_channel=50
    12-08 11:02:11.000 I/GlobalKeyInterceptor: onReceive keyCode = 172
    12-08 11:02:12.000 I/PartnerTV+: PartnerTV+ GUIDE intent sent with channel: 3
    """
    signals = parse_live_button_logs(log_text, expected_channel=50)

    phases = {phase.phase: phase for phase in signals.phases}
    assert phases["PHASE1"].observed_channel == 50
    assert phases["PHASE3"].observed_channel == 3
    assert phases["PHASE3"].raw_excerpt and "channel: 3" in phases["PHASE3"].raw_excerpt
