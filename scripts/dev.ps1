param(
  [Parameter(Position = 0)]
  [ValidateSet("up","down","ps","logs","api")]
  [string]$Command = "up"
)

$composeFile = "infra/compose/docker-compose.yml"
$envFile = "infra/compose/.env"
$envExample = "infra/compose/.env.example"

if (-not (Test-Path $envFile)) {
  if (-not (Test-Path $envExample)) {
    throw "Missing $envFile and $envExample"
  }

  Copy-Item $envExample $envFile
  Write-Host "Created $envFile from $envExample. Edit it if needed."
}

switch ($Command) {
  "up"   { docker compose -f $composeFile --env-file $envFile up -d --build; break }
  "down" { docker compose -f $composeFile --env-file $envFile down; break }
  "ps"   { docker compose -f $composeFile --env-file $envFile ps; break }
  "logs" { docker compose -f $composeFile --env-file $envFile logs -f --tail=200; break }
  "api"  { docker compose -f $composeFile --env-file $envFile up -d --build api; break }
}
