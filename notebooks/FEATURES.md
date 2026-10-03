# Physical feature dictionary

All features are calculated from the ten original measurements before scaling.
The raw feature frame is used for interpretation and data-quality checks.
StandardScaler then fits its means and standard deviations on fit rows only;
its output is dimensionless and must not be presented as a byte or packet count.
Labels, attack categories and row IDs are never inputs to these features.

For example, 100 source bytes, 50 destination bytes, 4 source packets and
2 destination packets give **150 bytes**, **6 packets**, **25 bytes/packet**
in each direction, an exact byte ratio of **2**, and signed byte balance **1/3**.

Undefined divisions use a zero sentinel and an explicit indicator. The sentinel
is a finite model representation, not an observed zero ratio. The separately
named smoothed ratio adds one byte to both counts and is always defined.
Zero packet counts paired with positive bytes are accepted with the zero-packet
flag and counted as inconsistencies in the quality report, rather than silently
inventing a packet count. TTL=0 is retained and does not trigger the low-TTL
indicator; the 1-9 rule is a candidate predictor, not evidence of an attack.

Inputs must be finite and nonnegative. Byte/packet counts are integral and their
totals remain within exact float64 integer precision (2^53 - 1). TTL values are
integers from 0 through 255. Missing measurements fail explicitly. Logs use one
reference unit of the original input; rate and load are retained in the CSV's
original units and are not reconstructed from duration or bytes. Confirm those
exporter units when applying the model to a new traffic collector.

These are project-defined derived features built on the supplied CSV fields;
[the original UNSW dataset page](https://research.unsw.edu.au/projects/unsw-nb15-dataset)
identifies the original feature-description file. The dictionary below is the
canonical definition of **this workflow**, including its denominator conventions.

**Feature schema 2:** added the exact byte ratio and denominator flags, and made
signed byte balance use the exact byte total. Retrain older workflow artifacts
with the documented runner. Historical notebook cells and dashboard models
retain their earlier recipes and are preserved separately.

| Feature | Meaning | Unit before scaling | Formula | Zero policy |
| --- | --- | --- | --- | --- |
| sbytes | Source-to-destination byte count | bytes | measured raw input | Retain recorded zero; never substitute a median. |
| dbytes | Destination-to-source byte count | bytes | measured raw input | Retain recorded zero; never substitute a median. |
| spkts | Source-to-destination packet count | packets | measured raw input | Retain recorded zero; never substitute a median. |
| dpkts | Destination-to-source packet count | packets | measured raw input | Retain recorded zero; never substitute a median. |
| dur | Recorded connection duration | seconds | measured raw input | Retain recorded zero; never substitute a median. |
| rate | Connection rate supplied by the dataset; not recomputed | original dataset rate units | measured raw input | Retain recorded zero; never substitute a median. |
| sload | Recorded source load; not recomputed | original dataset load units | measured raw input | Retain recorded zero; never substitute a median. |
| dload | Recorded destination load; not recomputed | original dataset load units | measured raw input | Retain recorded zero; never substitute a median. |
| sttl | Recorded source packet time-to-live value | TTL value | measured raw input | Retain recorded zero; never substitute a median. |
| dttl | Recorded destination packet time-to-live value | TTL value | measured raw input | Retain recorded zero; never substitute a median. |
| bytes_total | Total recorded bytes in both directions | bytes | sbytes + dbytes | 0 when both byte counts are 0. |
| pkts_total | Total recorded packets in both directions | packets | spkts + dpkts | 0 when both packet counts are 0. |
| bytes_per_pkt_src | Source bytes per recorded source packet | bytes/packet | sbytes / spkts | If spkts=0, use 0 sentinel and src_zero_pkts=1. |
| bytes_per_pkt_dst | Destination bytes per recorded destination packet | bytes/packet | dbytes / dpkts | If dpkts=0, use 0 sentinel and dst_zero_pkts=1. |
| bytes_ratio | Exact source/destination byte ratio when defined | dimensionless | sbytes / dbytes | If dbytes=0, use 0 sentinel and dst_zero_bytes=1. |
| bytes_ratio_smoothed | Source/destination byte ratio with a one-byte pseudocount | dimensionless | (sbytes + 1 byte) / (dbytes + 1 byte) | Always defined; both zero gives 1. This is a smoothed ratio, not an exact measured ratio. |
| bytes_diff_normalized | Signed directional byte balance: -1 destination-only, +1 source-only | dimensionless [-1, 1] | (sbytes - dbytes) / bytes_total | If bytes_total=0, use 0 sentinel and zero_total_bytes=1. |
| src_zero_pkts | Source bytes-per-packet denominator is zero | binary 0/1 | 1 if spkts == 0 else 0 | 1 includes both all-zero and inconsistent positive-byte/zero-packet inputs. |
| dst_zero_pkts | Destination bytes-per-packet denominator is zero | binary 0/1 | 1 if dpkts == 0 else 0 | 1 includes both all-zero and inconsistent positive-byte/zero-packet inputs. |
| dst_zero_bytes | Exact byte-ratio denominator is zero | binary 0/1 | 1 if dbytes == 0 else 0 | Disambiguates the undefined-ratio sentinel from a measured zero ratio. |
| zero_total_bytes | No recorded bytes in either direction | binary 0/1 | 1 if bytes_total == 0 else 0 | Disambiguates undefined byte balance from equal nonzero byte counts. |
| src_low_ttl | Candidate low source TTL indicator; does not prove an attack | binary 0/1 | 1 if 0 < sttl < 10 else 0 | TTL=0 is not marked low. No missing TTL is inferred. |
| dst_low_ttl | Candidate low destination TTL indicator; does not prove an attack | binary 0/1 | 1 if 0 < dttl < 10 else 0 | TTL=0 is not marked low. No missing TTL is inferred. |
| log1p_sbytes | Natural-log compression of raw sbytes; no clipping of scaled values | dimensionless log value | ln(1 + sbytes / 1 reference unit [bytes]) | Raw zero maps to zero. Negative/nonfinite raw measurements are rejected. |
| log1p_dbytes | Natural-log compression of raw dbytes; no clipping of scaled values | dimensionless log value | ln(1 + dbytes / 1 reference unit [bytes]) | Raw zero maps to zero. Negative/nonfinite raw measurements are rejected. |
| log1p_dur | Natural-log compression of raw dur; no clipping of scaled values | dimensionless log value | ln(1 + dur / 1 reference unit [seconds]) | Raw zero maps to zero. Negative/nonfinite raw measurements are rejected. |
| log1p_rate | Natural-log compression of raw rate; no clipping of scaled values | dimensionless log value | ln(1 + rate / 1 reference unit [original dataset rate units]) | Raw zero maps to zero. Negative/nonfinite raw measurements are rejected. |
| log1p_sload | Natural-log compression of raw sload; no clipping of scaled values | dimensionless log value | ln(1 + sload / 1 reference unit [original dataset load units]) | Raw zero maps to zero. Negative/nonfinite raw measurements are rejected. |
| log1p_dload | Natural-log compression of raw dload; no clipping of scaled values | dimensionless log value | ln(1 + dload / 1 reference unit [original dataset load units]) | Raw zero maps to zero. Negative/nonfinite raw measurements are rejected. |

## Completion checks

The corrected notebook checks every row of both raw CSVs. It verifies exact
byte/packet totals, nonnegative integer counts, raw-input preservation, finite
ratios, zero-denominator flags, signed balance bounds, logarithm round trips and
TTL rules. The model pipeline applies `raw_features`, then `scaler`, then `model`.
Unit tests include all-zero traffic, positive bytes with zero packets, TTL
boundaries, invalid counts, and rejection of scaled values as physical features.
The feature catalog and quality report are saved beside the new model artifact.
