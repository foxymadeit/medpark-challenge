param(
    [string]$ApiBaseUrl = "http://127.0.0.1:8000",
    [string]$MailpitBaseUrl = "http://localhost:8025",
    [string[]]$ExpectedRecipients = @()
)

$ErrorActionPreference = "Stop"

if ($ExpectedRecipients.Count -eq 0) {
    $ExpectedRecipients = @(
        $env:MOM_RECIPIENTS_MEDICAL -split "," |
            ForEach-Object { $_.Trim() } |
            Where-Object { $_ }
    )
}

if ($ExpectedRecipients.Count -eq 0) {
    throw "Pass -ExpectedRecipients or set MOM_RECIPIENTS_MEDICAL in this shell."
}

$runId = [guid]::NewGuid().ToString("N").Substring(0, 8)
$title = "SMTP Smoke Test $runId"
$subject = "MoM | Medical | $title"
$summary = "Local Mailpit delivery check $runId."

$body = @{
    minutes = @{
        title = $title
        meeting_type = "medical"
        language = "ro"
        summary = $summary
        attendees = @("Dr. Test")
        decisions = @("Approve the local SMTP test")
        action_items = @(
            @{
                text = "Confirm this test email"
                owner = "Dr. Test"
                deadline = "2026-09-30"
                source_quote = "Please confirm the local SMTP test."
            }
        )
    }
} | ConvertTo-Json -Depth 8

$response = Invoke-RestMethod `
    -Uri "$($ApiBaseUrl.TrimEnd('/'))/email/send" `
    -Method Post `
    -ContentType "application/json" `
    -Body $body

if ($response.status -ne "sent") {
    throw "API delivery status was '$($response.status)' instead of 'sent'."
}
if ($response.accepted_count -ne $ExpectedRecipients.Count -or $response.refused_count -ne 0) {
    throw "Expected $($ExpectedRecipients.Count) accepted and 0 refused; got $($response.accepted_count) accepted and $($response.refused_count) refused."
}

$mailpit = Invoke-RestMethod -Uri "$($MailpitBaseUrl.TrimEnd('/'))/api/v1/messages"
$message = $mailpit.messages | Where-Object { $_.Subject -eq $subject } | Select-Object -First 1
if (-not $message) {
    throw "API reported success, but Mailpit did not contain '$subject'."
}

$detail = Invoke-RestMethod -Uri "$($MailpitBaseUrl.TrimEnd('/'))/api/v1/message/$($message.ID)"
$actualRecipients = @($detail.Bcc | ForEach-Object { $_.Address } | Sort-Object)
$expectedSorted = @($ExpectedRecipients | Sort-Object)
if (($actualRecipients -join "|") -ne ($expectedSorted -join "|")) {
    throw "Mailpit recipients did not match. Expected: $($expectedSorted -join ', '); actual: $($actualRecipients -join ', ')."
}
if (-not $detail.Text.Contains($summary)) {
    throw "Mailpit message is missing the expected plain-text summary."
}
if (-not $detail.HTML.Contains("Confirm this test email")) {
    throw "Mailpit message is missing the expected HTML action item."
}

Write-Host "PASS: API returned sent; Mailpit received the message, expected recipients, text, and HTML."
Write-Host "Subject: $subject"
