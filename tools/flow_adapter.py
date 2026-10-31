import math
from typing import Literal

# Python CICFlowMeter column -> CIC-IDS2017 model feature.
FEATURE_MAP = {
    "Destination Port": "dst_port",
    "Flow Duration": "flow_duration",
    "Total Fwd Packets": "tot_fwd_pkts",
    "Total Backward Packets": "tot_bwd_pkts",
    "Total Length of Fwd Packets": "totlen_fwd_pkts",
    "Total Length of Bwd Packets": "totlen_bwd_pkts",
    "Fwd Packet Length Max": "fwd_pkt_len_max",
    "Fwd Packet Length Min": "fwd_pkt_len_min",
    "Fwd Packet Length Mean": "fwd_pkt_len_mean",
    "Fwd Packet Length Std": "fwd_pkt_len_std",
    "Bwd Packet Length Max": "bwd_pkt_len_max",
    "Bwd Packet Length Min": "bwd_pkt_len_min",
    "Flow Bytes/s": "flow_byts_s",
    "Flow Packets/s": "flow_pkts_s",
    "Flow IAT Mean": "flow_iat_mean",
    "Flow IAT Std": "flow_iat_std",
    "Flow IAT Max": "flow_iat_max",
    "Flow IAT Min": "flow_iat_min",
    "Fwd IAT Total": "fwd_iat_tot",
    "Fwd IAT Mean": "fwd_iat_mean",
    "Fwd IAT Std": "fwd_iat_std",
    "Fwd IAT Max": "fwd_iat_max",
    "Fwd IAT Min": "fwd_iat_min",
    "Bwd IAT Total": "bwd_iat_tot",
    "Bwd IAT Mean": "bwd_iat_mean",
    "Bwd IAT Std": "bwd_iat_std",
    "Bwd IAT Max": "bwd_iat_max",
    "Bwd IAT Min": "bwd_iat_min",
    "Fwd PSH Flags": "fwd_psh_flags",
    "Bwd PSH Flags": "bwd_psh_flags",
    "Fwd URG Flags": "fwd_urg_flags",
    "Bwd URG Flags": "bwd_urg_flags",
    "Fwd Header Length": "fwd_header_len",
    "Bwd Header Length": "bwd_header_len",
    "Fwd Packets/s": "fwd_pkts_s",
    "Bwd Packets/s": "bwd_pkts_s",
    "Min Packet Length": "pkt_len_min",
    "Max Packet Length": "pkt_len_max",
    "Packet Length Mean": "pkt_len_mean",
    "Packet Length Std": "pkt_len_std",
    "Packet Length Variance": "pkt_len_var",
    "FIN Flag Count": "fin_flag_cnt",
    "SYN Flag Count": "syn_flag_cnt",
    "RST Flag Count": "rst_flag_cnt",
    "ACK Flag Count": "ack_flag_cnt",
    "URG Flag Count": "urg_flag_cnt",
    "CWE Flag Count": "cwr_flag_count",
    "ECE Flag Count": "ece_flag_cnt",
    "Down/Up Ratio": "down_up_ratio",
    "Avg Fwd Segment Size": "fwd_seg_size_avg",
    "Avg Bwd Segment Size": "bwd_seg_size_avg",
    "Fwd Header Length.1": "fwd_header_len",
    "Fwd Avg Bytes/Bulk": "fwd_byts_b_avg",
    "Fwd Avg Packets/Bulk": "fwd_pkts_b_avg",
    "Fwd Avg Bulk Rate": "fwd_blk_rate_avg",
    "Bwd Avg Bytes/Bulk": "bwd_byts_b_avg",
    "Bwd Avg Packets/Bulk": "bwd_pkts_b_avg",
    "Bwd Avg Bulk Rate": "bwd_blk_rate_avg",
    "Subflow Fwd Packets": "subflow_fwd_pkts",
    "Subflow Fwd Bytes": "subflow_fwd_byts",
    "Subflow Bwd Packets": "subflow_bwd_pkts",
    "Subflow Bwd Bytes": "subflow_bwd_byts",
    "Init_Win_bytes_forward": "init_fwd_win_byts",
    "Init_Win_bytes_backward": "init_bwd_win_byts",
    "min_seg_size_forward": "fwd_seg_size_min",
    "Active Mean": "active_mean",
    "Active Std": "active_std",
    "Active Max": "active_max",
    "Active Min": "active_min",
    "Idle Mean": "idle_mean",
    "Idle Std": "idle_std",
    "Idle Max": "idle_max",
    "Idle Min": "idle_min",
}

# Native CICFlowMeter headers that differ from the model feature names or
# shortened CSV headers used by the local flow extractor.
HEADER_ALIASES = {
    "Destination Port": ("Dst Port",),
    "Total Fwd Packets": ("Total Fwd Packet",),
    "Total Backward Packets": ("Total Bwd packets",),
    "Total Length of Fwd Packets": ("Total Length of Fwd Packet",),
    "Total Length of Bwd Packets": ("Total Length of Bwd Packet",),
    "Min Packet Length": ("Packet Length Min",),
    "Max Packet Length": ("Packet Length Max",),
    "Packet Length Mean": ("Packet Length Mean",),
    "Packet Length Std": ("Packet Length Std",),
    "Packet Length Variance": ("Packet Length Variance",),
    "CWE Flag Count": ("CWR Flag Count",),
    "Avg Fwd Segment Size": ("Fwd Segment Size Avg",),
    "Avg Bwd Segment Size": ("Bwd Segment Size Avg",),
    "Fwd Header Length.1": ("Fwd Header Length",),
    "Fwd Avg Bytes/Bulk": ("Fwd Bytes/Bulk Avg",),
    "Fwd Avg Packets/Bulk": ("Fwd Packet/Bulk Avg",),
    "Fwd Avg Bulk Rate": ("Fwd Bulk Rate Avg",),
    "Bwd Avg Bytes/Bulk": ("Bwd Bytes/Bulk Avg",),
    "Bwd Avg Packets/Bulk": ("Bwd Packet/Bulk Avg",),
    "Bwd Avg Bulk Rate": ("Bwd Bulk Rate Avg",),
    "Init_Win_bytes_forward": ("FWD Init Win Bytes",),
    "Init_Win_bytes_backward": ("Bwd Init Win Bytes",),
    "min_seg_size_forward": ("Fwd Seg Size Min",),
}

# Features whose training values are in microseconds, while this
# extractor reports seconds.
TIME_FEATURES = {
    "Flow Duration",
    "Flow IAT Mean", "Flow IAT Std", "Flow IAT Max", "Flow IAT Min",
    "Fwd IAT Total", "Fwd IAT Mean", "Fwd IAT Std",
    "Fwd IAT Max", "Fwd IAT Min",
    "Bwd IAT Total", "Bwd IAT Mean", "Bwd IAT Std",
    "Bwd IAT Max", "Bwd IAT Min",
    "Active Mean", "Active Std", "Active Max", "Active Min",
    "Idle Mean", "Idle Std", "Idle Max", "Idle Min",
}



def adapt_flow(
    row: dict,
    expected_features: list[str],
    *,
    time_unit: Literal["seconds", "microseconds"] = "seconds",
) -> dict:
    """Map a flow row to model features.

    CICFlowMeter exports duration and IAT values in microseconds. The
    shortened flow CSV generated by the local extractor uses seconds, so its
    values are converted by default. Callers passing raw CICFlowMeter values
    must set ``time_unit="microseconds"``.
    """
    if time_unit not in {"seconds", "microseconds"}:
        raise ValueError("time_unit must be 'seconds' or 'microseconds'")

    result = {}

    for feature in expected_features:
        if feature not in FEATURE_MAP:
            raise ValueError(
                f"No mapping defined for model feature: {feature}"
            )

        source = FEATURE_MAP[feature]

        candidates = (source, feature, *HEADER_ALIASES.get(feature, ()))
        raw_value = next(
            (row[name] for name in candidates if name in row),
            None,
        )
        if raw_value is None:
            raise ValueError(
                f"Missing column for {feature!r}. "
                f"Expected one of {candidates!r}."
            )

        try:
            value = float(raw_value)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"Feature {feature!r} is not numeric: {raw_value!r}"
            ) from exc

        if not math.isfinite(value):
            raise ValueError(
                f"Feature {feature!r} is not finite: {value}"
            )

        if feature in TIME_FEATURES and time_unit == "seconds":
            value *= 1_000_000

        result[feature] = value

    return result
