param(
    [string]$OutputPath = "IoT_Autoencoder_Viva.pptx"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$outFile = Join-Path $root $OutputPath
$buildDir = Join-Path $root ".pptx_build"

if (Test-Path -LiteralPath $buildDir) {
    Remove-Item -LiteralPath $buildDir -Recurse -Force
}
New-Item -ItemType Directory -Path $buildDir | Out-Null
New-Item -ItemType Directory -Path (Join-Path $buildDir "_rels") | Out-Null
New-Item -ItemType Directory -Path (Join-Path $buildDir "ppt") | Out-Null
New-Item -ItemType Directory -Path (Join-Path $buildDir "ppt\_rels") | Out-Null
New-Item -ItemType Directory -Path (Join-Path $buildDir "ppt\slides") | Out-Null
New-Item -ItemType Directory -Path (Join-Path $buildDir "docProps") | Out-Null

function XmlEscape([string]$s) {
    return [System.Security.SecurityElement]::Escape($s)
}

function Emu([double]$inches) {
    return [int][Math]::Round($inches * 914400)
}

function ColorFill([string]$hex) {
    if ([string]::IsNullOrWhiteSpace($hex)) { return "" }
    return "<a:solidFill><a:srgbClr val=`"$hex`"/></a:solidFill>"
}

function RectShape([int]$id, [double]$x, [double]$y, [double]$w, [double]$h, [string]$fill, [string]$line = "D6DEE8", [int]$radius = 0) {
    $geom = if ($radius -gt 0) { "roundRect" } else { "rect" }
    $fillXml = ColorFill $fill
    $lineXml = if ($line -eq "none") { "<a:ln><a:noFill/></a:ln>" } else { "<a:ln w=`"12700`"><a:solidFill><a:srgbClr val=`"$line`"/></a:solidFill></a:ln>" }
    return @"
<p:sp>
  <p:nvSpPr><p:cNvPr id="$id" name="Shape $id"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>
  <p:spPr>
    <a:xfrm><a:off x="$(Emu $x)" y="$(Emu $y)"/><a:ext cx="$(Emu $w)" cy="$(Emu $h)"/></a:xfrm>
    <a:prstGeom prst="$geom"><a:avLst/></a:prstGeom>
    $fillXml
    $lineXml
  </p:spPr>
  <p:txBody><a:bodyPr/><a:lstStyle/><a:p><a:endParaRPr lang="en-GB"/></a:p></p:txBody>
</p:sp>
"@
}

function TextBox([int]$id, [double]$x, [double]$y, [double]$w, [double]$h, [object[]]$lines, [int]$fontSize = 20, [string]$color = "172033", [bool]$bold = $false, [string]$fill = "", [string]$line = "none") {
    $fillXml = if ($fill) { ColorFill $fill } else { "<a:noFill/>" }
    $lineXml = if ($line -eq "none") { "<a:ln><a:noFill/></a:ln>" } else { "<a:ln w=`"12700`"><a:solidFill><a:srgbClr val=`"$line`"/></a:solidFill></a:ln>" }
    $paras = ""
    foreach ($item in $lines) {
        $txt = [string]$item
        $isBullet = $txt.StartsWith("• ")
        if ($isBullet) {
            $txt = $txt.Substring(2)
            $paras += "<a:p><a:pPr marL=`"228600`" indent=`"-171450`"><a:buChar char=`"•`"/></a:pPr><a:r><a:rPr lang=`"en-GB`" sz=`"$($fontSize * 100)`"><a:solidFill><a:srgbClr val=`"$color`"/></a:solidFill></a:rPr><a:t>$(XmlEscape $txt)</a:t></a:r></a:p>"
        } else {
            $b = if ($bold) { " b=`"1`"" } else { "" }
            $paras += "<a:p><a:r><a:rPr lang=`"en-GB`" sz=`"$($fontSize * 100)`"$b><a:solidFill><a:srgbClr val=`"$color`"/></a:solidFill></a:rPr><a:t>$(XmlEscape $txt)</a:t></a:r></a:p>"
        }
    }
    return @"
<p:sp>
  <p:nvSpPr><p:cNvPr id="$id" name="TextBox $id"/><p:cNvSpPr txBox="1"/><p:nvPr/></p:nvSpPr>
  <p:spPr>
    <a:xfrm><a:off x="$(Emu $x)" y="$(Emu $y)"/><a:ext cx="$(Emu $w)" cy="$(Emu $h)"/></a:xfrm>
    <a:prstGeom prst="rect"><a:avLst/></a:prstGeom>
    $fillXml
    $lineXml
  </p:spPr>
  <p:txBody><a:bodyPr wrap="square" lIns="91440" tIns="45720" rIns="91440" bIns="45720"/><a:lstStyle/>$paras</p:txBody>
</p:sp>
"@
}

function ArrowLine([int]$id, [double]$x, [double]$y, [double]$w, [string]$color = "5B6B7F") {
    return @"
<p:cxnSp>
  <p:nvCxnSpPr><p:cNvPr id="$id" name="Arrow $id"/><p:cNvCxnSpPr/><p:nvPr/></p:nvCxnSpPr>
  <p:spPr>
    <a:xfrm><a:off x="$(Emu $x)" y="$(Emu $y)"/><a:ext cx="$(Emu $w)" cy="0"/></a:xfrm>
    <a:prstGeom prst="straightConnector1"><a:avLst/></a:prstGeom>
    <a:ln w="25400"><a:solidFill><a:srgbClr val="$color"/></a:solidFill><a:tailEnd type="none"/><a:headEnd type="triangle"/></a:ln>
  </p:spPr>
</p:cxnSp>
"@
}

function SlideXml([string]$title, [string]$bodyXml) {
    return @"
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sld xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
  <p:cSld name="$(XmlEscape $title)">
    <p:bg><p:bgPr><a:solidFill><a:srgbClr val="F7F9FC"/></a:solidFill></p:bgPr></p:bg>
    <p:spTree>
      <p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>
      <p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>
      $(RectShape 2 0 0 13.333 0.24 "17324D" "none")
      $(TextBox 3 0.55 0.42 11.8 0.55 @($title) 25 "17324D" $true)
      $(RectShape 4 0.55 1.05 12.2 0.02 "B8C4D6" "none")
      $bodyXml
    </p:spTree>
  </p:cSld>
  <p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr>
</p:sld>
"@
}

$slides = @()

$slides += SlideXml "Title & Overview" @"
$(TextBox 10 0.8 1.45 11.7 1.25 @("An Interactive IoT Network Anomaly Detection System Using Deep Autoencoders") 31 "172033" $true)
$(TextBox 11 0.85 2.78 5.6 0.85 @("BSc Software Engineering final-year viva","Student: <Your Name>","Supervisor: <Supervisor Name>") 18 "334155")
$(TextBox 12 0.85 4.05 10.8 0.75 @("One-sentence summary: a benign-trained autoencoder scores IoT-23 network flows and presents anomalies through an interactive Streamlit dashboard.") 18 "172033" $false "FFFFFF" "D6DEE8")
$(TextBox 13 0.85 5.25 10.8 0.55 @("Python  |  TensorFlow/Keras  |  scikit-learn  |  Streamlit") 18 "17324D" $true)
"@

$slides += SlideXml "Problem & Motivation" @"
$(TextBox 10 0.85 1.35 5.8 4.8 @("• IoT devices are often resource-constrained and inconsistently secured","• Mirai-style botnets show how weak IoT devices can be weaponised","• Network behaviour is heterogeneous across device types and services","• New attacks may appear before high-quality labels are available") 20 "172033")
$(TextBox 11 7.1 1.45 4.9 1.0 @("Core challenge") 24 "FFFFFF" $true "17324D" "none")
$(TextBox 12 7.1 2.45 4.9 1.9 @("Detect suspicious network flows when complete labelled attack data is limited or unavailable.") 24 "172033" $true "FFFFFF" "D6DEE8")
$(TextBox 13 7.1 4.75 4.9 0.85 @("Unsupervised anomaly detection fits this setting because it models normal behaviour first.") 17 "334155" $false "EAF0F7" "D6DEE8")
"@

$slides += SlideXml "Aim & Objectives" @"
$(TextBox 10 0.85 1.35 11.4 0.9 @("Aim: design and evaluate an interactive system for detecting anomalous IoT network flows using a deep autoencoder trained on benign traffic.") 20 "172033" $true "FFFFFF" "D6DEE8")
$(TextBox 11 0.95 2.55 10.9 3.7 @("• Preprocess IoT-23 Zeek flow logs into a model-ready tabular dataset","• Train an unsupervised autoencoder on benign flows and derive an MSE threshold","• Implement an Isolation Forest baseline for comparison","• Evaluate detection with precision, recall, F1-score and PR-AUC","• Build a Streamlit dashboard for threshold exploration and anomaly inspection") 21 "172033")
"@

$slides += SlideXml "Dataset & Features (IoT-23)" @"
$(TextBox 10 0.85 1.35 5.5 4.7 @("• Public IoT-23 / CTU-IoT-23 flow-level traffic dataset","• Zeek conn.log.labeled style records from real IoT network scenarios","• Suitable because it includes benign and malicious-labelled connection flows","• Labels are used for evaluation, not for autoencoder training") 19 "172033")
$(TextBox 11 7.0 1.38 5.25 0.45 @("Visual space: feature/data snapshot") 17 "5B6B7F" $true)
$(RectShape 12 7.0 1.92 5.3 3.8 "FFFFFF" "B8C4D6")
$(TextBox 13 7.25 2.2 4.75 2.95 @("Zeek flow features","• proto, service, conn_state","• duration, bytes, packets","• history, tunnel fields","• label, detailed-label","• UID/IP columns dropped for generalisation") 17 "172033")
"@

$slides += SlideXml "System Architecture & Models" @"
$(TextBox 10 0.75 1.22 2.1 0.78 @("IoT-23 Zeek flows") 15 "172033" $true "FFFFFF" "AAB7C8")
$(ArrowLine 11 2.95 1.61 0.75)
$(TextBox 12 3.75 1.22 2.1 0.78 @("Preprocessing","scale + one-hot") 15 "172033" $true "FFFFFF" "AAB7C8")
$(ArrowLine 13 5.95 1.61 0.75)
$(TextBox 14 6.75 0.82 2.15 0.72 @("Autoencoder","MSE score") 14 "FFFFFF" $true "17324D" "none")
$(TextBox 15 6.75 1.72 2.15 0.72 @("Isolation Forest","baseline") 14 "17324D" $true "EAF0F7" "AAB7C8")
$(ArrowLine 16 9.05 1.61 0.75)
$(TextBox 17 9.85 1.22 2.55 0.78 @("Streamlit dashboard") 15 "172033" $true "FFFFFF" "AAB7C8")
$(TextBox 18 0.85 3.15 5.55 2.55 @("Model logic","• Autoencoder reconstructs benign flow vectors","• High reconstruction MSE indicates poor fit to benign behaviour","• Threshold converts score into anomaly flag","• Isolation Forest isolates sparse/outlying points as baseline") 19 "172033")
$(TextBox 19 7.0 3.15 5.25 2.55 @("Why unsupervised?","• Practical attack labels may be incomplete","• New IoT attacks can appear after deployment","• Benign-only training supports anomaly discovery") 19 "172033")
"@

$slides += SlideXml "Evaluation & Results" @"
$(TextBox 10 0.85 1.35 5.6 4.8 @("Evaluation protocol","• Stratified 70 / 15 / 15 train, validation and test split","• Autoencoder trained on benign training flows only","• Threshold calibrated from benign validation MSE","• Held-out test set scored by autoencoder and Isolation Forest") 19 "172033")
$(TextBox 11 7.0 1.35 5.2 3.4 @("Results placeholders","• Precision AE: <PRECISION_AE>","• Recall AE: <RECALL_AE>","• F1-score AE: <F1_AE>","• PR-AUC AE: <PR_AUC_AE>","• F1-score IF: <F1_IF>","• PR-AUC IF: <PR_AUC_IF>") 19 "172033" $false "FFFFFF" "D6DEE8")
$(TextBox 12 7.0 5.05 5.2 0.75 @("Comparison focus: thresholded detection quality plus ranking quality from continuous anomaly scores.") 16 "334155")
"@

$slides += SlideXml "Demo & Dashboard" @"
$(TextBox 10 0.85 1.35 5.45 4.95 @("Live demo plan","• Overview: rows scored, rows flagged and headline metrics","• Reconstruction-error histogram with threshold line","• Prepare Model: adjustable session threshold slider","• Detection Results: ranked anomalous flow table","• Export anomaly CSV / metrics evidence") 19 "172033")
$(TextBox 11 7.0 1.38 5.25 0.45 @("Visual space: dashboard screenshot") 17 "5B6B7F" $true)
$(RectShape 12 7.0 1.92 5.3 3.75 "FFFFFF" "B8C4D6")
$(TextBox 13 7.25 2.25 4.75 2.6 @("Dashboard screenshot placeholder","Histogram  |  Threshold slider","Anomaly table  |  Metrics cards") 20 "5B6B7F")
$(TextBox 14 0.95 6.15 10.9 0.55 @("Admin value: threshold control makes the false-positive / false-negative trade-off visible during investigation.") 17 "17324D" $true)
"@

$slides += SlideXml "Limitations, Ethics & Future Work" @"
$(TextBox 10 0.85 1.35 5.55 4.6 @("Limitations and ethics","• Batch CSV scoring, not live network capture","• Results depend on IoT-23 scenario and selected threshold","• Concept drift may change benign behaviour over time","• Reconstruction MSE is not a calibrated attack probability","• Public/anonymised benchmark data reduces privacy risk") 19 "172033")
$(TextBox 11 7.0 1.35 5.25 4.05 @("Future work","• Integrate a controlled real-time Zeek ingestion pipeline","• Evaluate on more IoT-23 scenarios and external datasets","• Add adaptive thresholds and drift monitoring","• Improve explainability and analyst feedback loops") 20 "172033" $false "FFFFFF" "D6DEE8")
$(TextBox 12 0.9 6.05 10.9 0.55 @("Closing message: the artefact demonstrates an end-to-end ML engineering pipeline with transparent evaluation and an examiner-facing dashboard.") 17 "17324D" $true)
"@

$contentTypes = @"
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
  <Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>
  <Override PartName="/ppt/presentation.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/>
  <Override PartName="/ppt/presProps.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presProps+xml"/>
  <Override PartName="/ppt/viewProps.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.viewProps+xml"/>
$(for ($i=1; $i -le 8; $i++) { "  <Override PartName=`"/ppt/slides/slide$i.xml`" ContentType=`"application/vnd.openxmlformats-officedocument.presentationml.slide+xml`"/>" })
</Types>
"@

Set-Content -LiteralPath (Join-Path $buildDir "[Content_Types].xml") -Value $contentTypes -Encoding UTF8

Set-Content -LiteralPath (Join-Path $buildDir "_rels\.rels") -Value @"
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="ppt/presentation.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
</Relationships>
"@ -Encoding UTF8

Set-Content -LiteralPath (Join-Path $buildDir "docProps\core.xml") -Value @"
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:dcmitype="http://purl.org/dc/dcmitype/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <dc:title>IoT Autoencoder Viva Presentation</dc:title>
  <dc:subject>Final-year BSc Software Engineering viva</dc:subject>
  <dc:creator>Codex</dc:creator>
  <cp:lastModifiedBy>Codex</cp:lastModifiedBy>
  <dcterms:created xsi:type="dcterms:W3CDTF">2026-05-06T00:00:00Z</dcterms:created>
  <dcterms:modified xsi:type="dcterms:W3CDTF">2026-05-06T00:00:00Z</dcterms:modified>
</cp:coreProperties>
"@ -Encoding UTF8

Set-Content -LiteralPath (Join-Path $buildDir "docProps\app.xml") -Value @"
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">
  <Application>Codex</Application>
  <PresentationFormat>On-screen Show (16:9)</PresentationFormat>
  <Slides>8</Slides>
</Properties>
"@ -Encoding UTF8

$sldIdLst = ""
$rels = "<?xml version=`"1.0`" encoding=`"UTF-8`" standalone=`"yes`"?><Relationships xmlns=`"http://schemas.openxmlformats.org/package/2006/relationships`">"
for ($i=1; $i -le 8; $i++) {
    $sldIdLst += "<p:sldId id=`"$($i + 255)`" r:id=`"rId$i`"/>"
    $rels += "<Relationship Id=`"rId$i`" Type=`"http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide`" Target=`"slides/slide$i.xml`"/>"
    Set-Content -LiteralPath (Join-Path $buildDir "ppt\slides\slide$i.xml") -Value $slides[$i-1] -Encoding UTF8
}
$rels += "<Relationship Id=`"rId9`" Type=`"http://schemas.openxmlformats.org/officeDocument/2006/relationships/presProps`" Target=`"presProps.xml`"/><Relationship Id=`"rId10`" Type=`"http://schemas.openxmlformats.org/officeDocument/2006/relationships/viewProps`" Target=`"viewProps.xml`"/></Relationships>"
Set-Content -LiteralPath (Join-Path $buildDir "ppt\_rels\presentation.xml.rels") -Value $rels -Encoding UTF8

Set-Content -LiteralPath (Join-Path $buildDir "ppt\presentation.xml") -Value @"
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:presentation xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
  <p:sldIdLst>$sldIdLst</p:sldIdLst>
  <p:sldSz cx="12192000" cy="6858000" type="wide"/>
  <p:notesSz cx="6858000" cy="9144000"/>
  <p:defaultTextStyle>
    <a:defPPr><a:defRPr lang="en-GB"/></a:defPPr>
  </p:defaultTextStyle>
</p:presentation>
"@ -Encoding UTF8

Set-Content -LiteralPath (Join-Path $buildDir "ppt\presProps.xml") -Value @"
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:presentationPr xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"/>
"@ -Encoding UTF8

Set-Content -LiteralPath (Join-Path $buildDir "ppt\viewProps.xml") -Value @"
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:viewPr xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"/>
"@ -Encoding UTF8

if (Test-Path -LiteralPath $outFile) {
    Remove-Item -LiteralPath $outFile -Force
}

Add-Type -AssemblyName System.IO.Compression.FileSystem
[System.IO.Compression.ZipFile]::CreateFromDirectory($buildDir, $outFile)
Remove-Item -LiteralPath $buildDir -Recurse -Force

Write-Output $outFile
