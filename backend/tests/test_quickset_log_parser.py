from backend.app.quickset_log_parser import parse_quickset_logs

GOOD_QUICKSET_LOG = """
12-08 10:02:43.628 D/QSDPRINT(13313): Entry QSP_get_device_brand, device ID: 0
12-08 10:02:43.645 D/QuicksetAPI(13282): Results: {"devices":[{"brand":"Samsung","id":"0","type":"TV"}]}
12-08 10:02:43.676 I/[UAPI]  (13313): quickset_sendstartsessionmsg startAutoSync
12-08 10:02:43.700 I/quickset_context: tv_device_name value:Samsung UHD
12-08 10:02:43.705 I/quickset_context: isTvSetup:true
12-08 10:02:43.991 D/QuicksetAPI(13282): --- EventHandler: content - {"volume_source":1}
12-08 10:02:44.013 D/SettingsSysUtils(13282): putInt, name:current_volume_source value:1
12-08 10:02:44.111 D/HdmiCecNetwork(  570): <Set Osd Name>
12-08 10:02:45.983 I/[UAPI]  (13313): quickset_sendendsessionmsg autosync success
"""

VOLUME_STB_TV_LOG = """
12-08 10:05:00.100 I/quickset: quickset_sendstartsessionmsg startAutoSync
12-08 10:05:00.150 I/quickset: tv_device_name value:LG OLED
12-08 10:05:00.200 I/quickset: isTvSetup:true
12-08 10:05:01.010 D/QuicksetAPI: {"volume_source":0}
12-08 10:05:01.050 D/QuicksetAPI: curVolSource:0
12-08 10:05:01.900 D/QuicksetAPI: {"volume_source":1}
12-08 10:05:01.940 D/QuicksetAPI: curVolSource:1
12-08 10:05:02.500 I/[UAPI]: quickset_sendendsessionmsg autosync completed
"""

BAD_QUICKSET_LOG = """
12-08 10:10:00.000 I/quickset: quickset_sendstartsessionmsg startAutoSync
12-08 10:10:00.100 I/quickset: tv_device_name value:Philips TV
12-08 10:10:00.150 I/quickset: isTvSetup:true
12-08 10:10:00.900 D/QuicksetAPI: {"volume_source":1}
12-08 10:10:01.500 W/quickset: tv_device_name value:Not Setup
12-08 10:10:01.520 W/quickset: isTvSetup:false
12-08 10:10:01.900 D/QuicksetAPI: {"volume_source":0}
12-08 10:10:02.000 E/quickset: autosync failed due to timeout
"""


def test_parse_quickset_logs_detects_successful_flow_and_history() -> None:
    signals = parse_quickset_logs(GOOD_QUICKSET_LOG)

    assert signals.quickset_seen is True
    assert signals.autosync_started is True
    assert signals.autosync_completed_successfully is True
    assert signals.autosync_error_codes == []
    assert signals.tv_brand_inferred == "Samsung"
    assert signals.tv_volume_events >= 1
    assert signals.tv_osd_events >= 1
    assert signals.volume_source_history[-1] == "TV"
    assert signals.tv_config_seen is True
    assert signals.tv_config_cleared_during_run is False


def test_parse_quickset_logs_tracks_transitions() -> None:
    signals = parse_quickset_logs(VOLUME_STB_TV_LOG)

    assert signals.autosync_started is True
    assert signals.autosync_completed_successfully is True
    assert signals.volume_source_history.count("STB") >= 1
    assert signals.volume_source_final == "TV"
    assert signals.stb_volume_events >= 1
    assert signals.volume_switch_events >= 1
    assert signals.tv_config_seen is True


def test_parse_quickset_logs_detects_config_clear_and_failures() -> None:
    signals = parse_quickset_logs(BAD_QUICKSET_LOG)

    assert signals.autosync_started is True
    assert signals.autosync_completed_successfully is False
    assert signals.autosync_failed is True
    assert signals.tv_config_seen is True
    assert signals.tv_config_cleared_during_run is True
    assert signals.stb_volume_events >= 1
    assert signals.volume_source_final == "STB"
    assert signals.autosync_error_codes
