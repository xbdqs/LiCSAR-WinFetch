# Suggested figure captions and table notes

## Figure 1
**Figure 1. LiCSAR-WinFetch acquisition, planning and validation architecture.** The upper path covers LiCSAR resource discovery, transfer/resume logic and LiCSBAS-ready GEOC organisation. The lower path shows inventory-only multi-frame temporal planning, structural/network checks and the bounded LiCSBAS step-02 interoperability test. Interferogram generation, inversion, mosaicking, cross-frame reference correction and LOS decomposition are outside the software scope.

## Figure 2
**Figure 2. File-level reliability logic and actual bounded benchmark output.** (a) File transfer follows resource resolution, local-size inspection, HTTP Range resume or clean restart, byte verification and atomic finalisation. (b) The bounded frame `124D_04854_171313` (2016-09-09 to 2016-10-03) produced six interferogram folders (12 IFG GeoTIFFs), eight auxiliary GEOC files and machine-readable/log outputs; all 20 planned benchmark files and all six interferogram pairs were complete and the LiCSBAS input-structure check passed.

## Figure 3
**Figure 3. Temporal coverage of the 22 Qilian LiCSAR frames.** Ascending and descending inventories are shown separately. The shaded band is the 22-frame maximum common calendar interval (2014-11-03 to 2023-09-07). Crosses mark the three 106D common epochs (2022-04-09, 2023-03-23 and 2023-08-14) that become isolated nodes under exact common-pair intersection.

## Figure 4
**Figure 4. Validation ladder and evidential boundary.** Validation progressed from six cross-platform CI jobs and 15 deterministic tests through 22 Qilian inventory scans, bounded 20-file acquisition/equivalence checks, complete SHA-256 coverage and successful LiCSBAS step-02 processing of all six benchmark interferograms. Later LiCSBAS processing, inversion and scientific interpretation were not tested.

## Table 1
**Table 1. Capability comparison between LiCSAR-WinFetch and the maintained LiCSBAS step-01 downloader.** “Not evaluated in this study” means no claim is made about the maintained downloader beyond the validation performed here. No transfer-speed comparison is intended.

## Table 2
**Table 2. Zero-download comparison of four temporal-selection modes for the two-frame 106D relative-orbit group over the common interval 2014-10-24 to 2023-09-07.** Exact common-pair intersection retained 1,970 pairs, equivalent to 94.0% of the smaller common-period network (2,096 pairs), and produced four connected components with three isolated common epochs. The 94.0% figure is relative to the smaller common-period network, not to both original frame networks.

## Table 3
**Table 3. Validation cases, observed evidence and interpretation limits.** The bounded LiCSBAS step-01 comparison used frame `124D_04854_171313` over 2016-09-09 to 2016-10-03 with GACOS disabled. All 20 expected output paths were present in both downloads; 19 files were byte-identical by SHA-256, including all 12 IFG products. The sole content difference was the representative MLI because the two downloaders selected different available source epochs. SHA-256 was computed for all 20 benchmark files on both sides.
