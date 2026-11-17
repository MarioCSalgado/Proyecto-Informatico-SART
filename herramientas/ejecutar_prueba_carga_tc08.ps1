$ErrorActionPreference = "Stop"

# Configuración editable de TC-08 (RF-7, RNF-R-1 y RNF-R-2).
$UrlApi = "http://127.0.0.1:8000"
$UrlObjetivo = "http://127.0.0.1:8000/centros/estado"
$DuracionSegundos = 30
$Correo = ""

$VariablesEntorno = @("SART_URL_OBJETIVO", "SART_COOKIE", "SART_DURACION_SEGUNDOS")
$ValoresAnteriores = @{}
foreach ($Nombre in $VariablesEntorno) {
    $ValoresAnteriores[$Nombre] = [Environment]::GetEnvironmentVariable($Nombre, "Process")
}

$Credencial = $null
$Clave = $null
$Cuerpo = $null
$SesionHttp = $null
$Cookie = $null

try {
    $UriApi = [uri]$UrlApi
    $UriObjetivo = [uri]$UrlObjetivo
    $HostsLocales = @("127.0.0.1", "::1")
    if ($UriApi.Host -notin $HostsLocales -or $UriObjetivo.Host -notin $HostsLocales) {
        throw "Por seguridad, la prueba solo admite API y destino en 127.0.0.1 o ::1."
    }

    $Pruebas = Join-Path $PSScriptRoot "pruebas_carga_tc08.test.mjs"
    $Arnes = Join-Path $PSScriptRoot "pruebas_carga_tc08.mjs"
    node --test $Pruebas
    if ($LASTEXITCODE -ne 0) { throw "Fallaron las pruebas del arnés TC-08." }

    if ([string]::IsNullOrWhiteSpace($Correo)) {
        $Credencial = Get-Credential -Message "Cuenta local de prueba (preferiblemente Subdirector)"
    }
    else {
        $Credencial = Get-Credential -UserName $Correo -Message "Cuenta local de prueba"
    }

    $Clave = $Credencial.GetNetworkCredential().Password
    $Cuerpo = @{ correo = $Credencial.UserName; contrasena = $Clave } | ConvertTo-Json -Compress
    $SesionHttp = [Microsoft.PowerShell.Commands.WebRequestSession]::new()
    Invoke-RestMethod `
        -Uri "$($UriApi.AbsoluteUri.TrimEnd('/'))/auth/sesion" `
        -Method Post `
        -ContentType "application/json" `
        -Body $Cuerpo `
        -WebSession $SesionHttp | Out-Null

    $Cookie = $SesionHttp.Cookies.GetCookies($UriApi) |
        Where-Object Name -eq "sart_sesion" |
        Select-Object -First 1
    if (-not $Cookie) { throw "No se obtuvo la cookie de sesión sart_sesion." }

    $env:SART_URL_OBJETIVO = $UrlObjetivo
    $env:SART_COOKIE = "sart_sesion=$($Cookie.Value)"
    $env:SART_DURACION_SEGUNDOS = "$DuracionSegundos"

    node $Arnes
    if ($LASTEXITCODE -ne 0) { throw "TC-08 no cumplió los umbrales de carga." }
}
finally {
    foreach ($Nombre in $VariablesEntorno) {
        $ValorAnterior = $ValoresAnteriores[$Nombre]
        if ($null -eq $ValorAnterior) {
            Remove-Item "Env:$Nombre" -ErrorAction SilentlyContinue
        }
        else {
            [Environment]::SetEnvironmentVariable($Nombre, $ValorAnterior, "Process")
        }
    }

    Remove-Variable Credencial, Clave, Cuerpo, SesionHttp, Cookie -ErrorAction SilentlyContinue
}
