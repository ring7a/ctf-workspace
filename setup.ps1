# Rebuilds the vendored CTF skills from the pinned upstream commit.
# Scaffolding (CLAUDE.md, .claude/agents, settings, templates) is tracked in git.
# Usage:  pwsh -File setup.ps1
$ErrorActionPreference = "Stop"
$Pinned = "c332c7be1b27cb64639a20124ac55ba916adef92"
$Root = $PSScriptRoot
$Tmp = Join-Path $env:TEMP ("ctf-skills-" + [guid]::NewGuid().ToString("N"))

Write-Host "Cloning ljagiello/ctf-skills @ $Pinned ..."
git clone https://github.com/ljagiello/ctf-skills $Tmp | Out-Null
git -C $Tmp checkout $Pinned | Out-Null

$Skills = "ctf-ai-ml","ctf-crypto","ctf-forensics","ctf-malware","ctf-misc",
          "ctf-osint","ctf-pwn","ctf-reverse","ctf-web","ctf-writeup","solve-challenge"
$Dest = Join-Path $Root ".claude\skills"
New-Item -ItemType Directory -Force -Path $Dest | Out-Null
foreach ($s in $Skills) {
    $target = Join-Path $Dest $s
    if (Test-Path $target) { Remove-Item -Recurse -Force $target }
    Copy-Item -Recurse (Join-Path $Tmp $s) $target
    Write-Host "  installed $s"
}
$Vendor = Join-Path $Root "tools\vendor-ctf-skills"
New-Item -ItemType Directory -Force -Path $Vendor | Out-Null
Copy-Item -Recurse -Force (Join-Path $Tmp "scripts") (Join-Path $Vendor "scripts")
Copy-Item -Force (Join-Path $Tmp "README.md") $Vendor
Copy-Item -Force (Join-Path $Tmp "LICENSE") $Vendor
$Pinned | Out-File -Encoding ascii (Join-Path $Vendor "PINNED_COMMIT.txt")

Remove-Item -Recurse -Force $Tmp
Write-Host "Done. $($Skills.Count) skills installed into $Dest"
