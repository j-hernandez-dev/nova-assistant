# Read-only evidence/hash verifier for the additive READY closure.
# This is not a scorer, benchmark, runtime preflight, or product test.
# No backend API, Application Turn, retrieval, admission, or file write.
[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
$kiRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../../..'))
$kiExternal = [System.IO.Path]::GetFullPath((Join-Path $kiRoot '../k8-certification-evidence'))
$kiFocal = Join-Path $kiExternal 'source-conflict-focal'
$kiDocs = Join-Path $kiRoot 'docs/knowledge_inputs_v1'
$kiR2 = Join-Path $kiDocs 'source_conflict_focal/revision_02'
$kiExecutionId = 'ki35-scf-r2-20261009T095331Z-369e17fb2b8e4ddab544668f9c0685f5'
$kiOutput = Join-Path $kiFocal ('executions/' + $kiExecutionId)
$kiHashCache = @{}
function Read-KiJson([string]$Path) {
    Get-Content -Raw -LiteralPath $Path | ConvertFrom-Json -AsHashtable
}
function Get-KiSha([string]$Path) {
    $resolved = [System.IO.Path]::GetFullPath($Path)
    if (!$kiHashCache.ContainsKey($resolved)) {
        $kiHashCache[$resolved] = (Get-FileHash -LiteralPath $resolved -Algorithm SHA256).Hash.ToLowerInvariant()
    }
    $kiHashCache[$resolved]
}
function Test-KiRows([string]$Label, $Rows, [string]$Base, [string]$Source) {
    $entries = @($Rows)
    $errors = @(foreach ($entry in $entries) {
        $target = $entry.path
        if (![System.IO.Path]::IsPathRooted($target)) { $target = Join-Path $Base $target }
        $expected = $entry.sha256
        if (!$expected) { $expected = $entry.expectedSha256 }
        if (!$expected -or !(Test-Path -LiteralPath $target -PathType Leaf)) {
            [ordered]@{path=$target; error='MISSING_FILE_OR_HASH'}
        } elseif ((Get-KiSha $target) -cne $expected) {
            [ordered]@{path=$target; error='SHA256_DRIFT'; expected=$expected; actual=Get-KiSha $target}
        }
    })
    [ordered]@{label=$Label; source=$Source; source_sha256=Get-KiSha $Source; checked=$entries.Count; errors=$errors}
}
function Test-KiIndex([string]$Label, [string]$Path) {
    $index = Read-KiJson $Path
    Test-KiRows $Label $index.files (Split-Path -Parent $Path) $Path
}
function Test-KiMap([string]$Label, [string]$Path) {
    $map = Read-KiJson $Path
    $rows = @(foreach ($key in $map.Keys) { @{path=$key; sha256=$map[$key]} })
    Test-KiRows $Label $rows $kiRoot $Path
}
$kiGroups = @(
    Test-KiIndex 'accepted_READY_audit' (Join-Path $kiDocs 'ready_audit/evidence_index.json')
    Test-KiIndex 'SCF_R2_delivery' (Join-Path $kiR2 ('execution_reports/' + $kiExecutionId + '/evidence_index.json'))
    Test-KiIndex 'SCF_R2_raw_Turn' (Join-Path $kiOutput 'evidence_index.json')
    Test-KiIndex 'SCF_R2_preexecution' (Join-Path $kiR2 'evidence_index.json')
    Test-KiIndex 'SCF_original_preexecution' (Join-Path $kiDocs 'source_conflict_focal/evidence_index.json')
    Test-KiIndex 'SCF_original_attempt' (Join-Path $kiDocs 'source_conflict_focal/execution_reports/ki35-scf-20261009T090822Z-ee53580ce47b44899a80bea492ab8fe5/evidence_index.json')
    Test-KiIndex 'K8_V2_original_35_attempts' (Join-Path $kiExternal 'executions/k8-v2-r4-20261009T022006Z-f30be3b928e743068980e90a20570029/evidence_index.json')
    Test-KiIndex 'R1_R2_focused_harness' (Join-Path $kiExternal 'focused-harness/r1-r2-20261009T040413Z-48a6a06a25cd447999922d54262863de/evidence_index.json')
    Test-KiMap 'preexisting_product_and_evidence_preservation' (Join-Path $kiFocal 'preparations/ki35-0d22fcf791d747439c446ef5c167b132/preservation_before.json')
    Test-KiMap 'original_focal_preservation' (Join-Path $kiFocal 'revision_02_preparation/6a58d0800b3041058813ed998952d572/original_preservation.json')
)
$kiFreezePath = Join-Path $kiR2 'freeze.json'
$kiFreeze = Read-KiJson $kiFreezePath
$kiGroups += Test-KiRows 'SCF_R2_699_pins' $kiFreeze.pins $kiRoot $kiFreezePath
$kiV2Path = Join-Path $kiRoot 'docs/knowledge_inputs_v2/revision_04/freeze_final_v2_r4.json'
$kiV2 = Read-KiJson $kiV2Path
$kiGroups += Test-KiRows 'K8_V2_R4_629_pins' (@($kiV2.pins) + @($kiV2.external_pins)) $kiRoot $kiV2Path
$kiArchivePath = Join-Path $kiDocs 'knowledge_context_capability_resolution_v1_head_evidence.json'
$kiArchive = Read-KiJson $kiArchivePath
$kiGroups += Test-KiRows 'current_regression_archived_11_artifacts' $kiArchive.artifacts $kiRoot $kiArchivePath
$kiHeadPath = Join-Path $kiDocs 'knowledge_context_capability_resolution_v1_head_evidence/head-closure-evidence.json'
$kiHead = Read-KiJson $kiHeadPath
$kiGroups += Test-KiRows 'current_regression_116_verified_references' $kiHead.integrityAfter.immutableHistoricalReferences $kiRoot $kiHeadPath
$kiCampaignPath = Join-Path $kiDocs 'k8_final_campaign_closure_manifest.json'
$kiCampaign = Read-KiJson $kiCampaignPath
$kiGroups += Test-KiRows 'original_K8_campaign_closure_artifacts' $kiCampaign.artifacts $kiRoot $kiCampaignPath
$kiOriginalPath = Join-Path $kiDocs 'k8_final_execution_manifest.json'
$kiOriginal = Read-KiJson $kiOriginalPath
$kiGroups += Test-KiRows 'original_K8_raw_inventory_identity' @($kiOriginal.artifacts.rawInventory) $kiRoot $kiOriginalPath
$kiRawInventoryPath = $kiOriginal.artifacts.rawInventory.path
$kiRawInventory = Read-KiJson $kiRawInventoryPath
$kiGroups += Test-KiRows 'original_K8_138_raw_artifacts' $kiRawInventory.artifacts $kiRoot $kiRawInventoryPath

$kiAnchors = @(
    @{path=(Join-Path $kiRoot 'docs/architecture/NOVA_KNOWLEDGE_INPUTS_ARQUITECTURA_V1.md');sha256='417807af0225f5e779f60497ad9d8b6d6ccabd02bf3c444bb1abf681c002d432'},
    @{path=(Join-Path $kiDocs 'ready_audit/ready_criteria_matrix.json');sha256='90f12505bba104d3c7bca67523c3fa13fab0cc1a93bf1a95efce3b489ba9c5d7'},
    @{path=$kiFreezePath;sha256='6bacb3109205c2a42a22be7794700e77b6f929f13852b6629278233a98832225'},
    @{path=$kiV2Path;sha256='23d7e7f0ce2c5edde5738724adad63a20113da01bcdd712487fd9d9c2e43c7b6'},
    @{path=(Join-Path $kiR2 ('execution_reports/'+$kiExecutionId+'/evidence_index.json'));sha256='8e530ca94af0134c40e705f19a81d2dd5d073dfd3c3723abd666473a65460312'}
)
$kiGroups += Test-KiRows 'accepted_identity_anchors' $kiAnchors $kiRoot (Join-Path $kiDocs 'ready_audit/evidence_index.json')
$kiFinalManifestPath = Join-Path $PSScriptRoot 'manifest.json'
if (Test-Path -LiteralPath $kiFinalManifestPath -PathType Leaf) {
    $kiFinalManifest = Read-KiJson $kiFinalManifestPath
    $kiGroups += Test-KiRows 'additive_READY_closure_manifest_files' $kiFinalManifest.files $kiRoot $kiFinalManifestPath
}

$kiErrors = @($kiGroups | ForEach-Object { $_.errors })
$kiGitHead = & git -C $kiRoot rev-parse HEAD
if ($kiGitHead -cne $kiArchive.head) { $kiErrors += 'CURRENT_PRODUCT_HEAD_DRIFT' }
$kiResult = Read-KiJson (Join-Path $kiOutput 'result.json')
$kiLedger = Read-KiJson (Join-Path $kiFocal 'ledger/6bacb3109205c2a42a22be7794700e77b6f929f13852b6629278233a98832225.json')
$kiOriginalLedger = Read-KiJson (Join-Path $kiFocal 'ledger/549adb90296c8eb92dec6fb70994c1e4d61d62d611670764e937531c44f83364.json')
[ordered]@{
    schema='knowledge-inputs-v1-additive-ready-integrity-1'
    checked_at=[DateTimeOffset]::UtcNow.ToString('o')
    status=if($kiErrors.Count){'BLOCKED'}else{'PASS'}
    errors=$kiErrors
    groups=$kiGroups
    unique_files_hashed=$kiHashCache.Count
    current_head=$kiGitHead
    model_inference_this_task=0
    retrieval_this_task=0
    admission_this_task=0
    product_suites_reexecuted=0
    quality_attempts_this_task=0
    raw_SCF_R2_result_unchanged=$kiResult.result.result
    raw_SCF_R2_counters_unchanged=$kiResult.counters
    SCF_R2_ledger_reservation_unchanged=$kiLedger.quality_attempt_reserved
    original_SCF_ledger_reservation_unchanged=$kiOriginalLedger.quality_attempt_reserved
    no_scorer_loaded_or_called=$true
    no_backend_request=$true
    no_file_write=$true
} | ConvertTo-Json -Depth 10
if ($kiErrors.Count) { exit 1 }
