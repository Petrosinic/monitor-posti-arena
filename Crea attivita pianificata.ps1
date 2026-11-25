<#
    Crea l'attivita' pianificata che controlla i posti mentre il PC e' acceso.

    Non sveglia il computer e non lo tiene sveglio: quando il PC e' spento o in
    sospensione non controlla niente, e riprende da solo appena torna acceso.

    Uso:
        .\Crea attivita pianificata.ps1              crea (o aggiorna) l'attivita'
        .\Crea attivita pianificata.ps1 -Minuti 5    ogni 5 minuti invece di 10
        .\Crea attivita pianificata.ps1 -Rimuovi     la cancella
#>

param(
    [int]$Minuti = 10,
    [switch]$Rimuovi
)

$ErrorActionPreference = "Stop"
$NomeAttivita = "Monitor posti Arena"
$Cartella = Split-Path -Parent $MyInvocation.MyCommand.Path

function Scrivi($testo, $colore = "Gray") { Write-Host $testo -ForegroundColor $colore }

# --- rimozione ------------------------------------------------------------ #

if ($Rimuovi) {
    try {
        Unregister-ScheduledTask -TaskName $NomeAttivita -Confirm:$false
        Scrivi "Attivita' '$NomeAttivita' rimossa. Il monitor non partira' piu' da solo." "Yellow"
    } catch {
        Scrivi "Nessuna attivita' chiamata '$NomeAttivita' da rimuovere." "Yellow"
    }
    return
}

# --- controlli preliminari ------------------------------------------------ #

$Script = Join-Path $Cartella "monitor_arena.py"
if (-not (Test-Path $Script)) {
    Scrivi "ERRORE: non trovo monitor_arena.py accanto a questo script." "Red"
    Scrivi "Questo file deve stare nella cartella del monitor." "Red"
    return
}

$Pythonw = Join-Path $env:LOCALAPPDATA "Python\pythoncore-3.14-64\pythonw.exe"
if (-not (Test-Path $Pythonw)) {
    # ripiego: cerco pythonw accanto al python nel PATH
    $py = (Get-Command python -ErrorAction SilentlyContinue).Source
    if ($py) { $Pythonw = Join-Path (Split-Path -Parent $py) "pythonw.exe" }
}
if (-not (Test-Path $Pythonw)) {
    Scrivi "ERRORE: non trovo pythonw.exe (il Python senza finestra)." "Red"
    Scrivi "Dimmelo e adattiamo il percorso." "Red"
    return
}

$Config = Join-Path $Cartella "config.json"
$telegramOk = $false
if (Test-Path $Config) {
    $c = Get-Content $Config -Raw | ConvertFrom-Json
    $telegramOk = [bool]$c.telegram.bot_token -and [bool]$c.telegram.chat_id
}

Scrivi ""
Scrivi "Configurazione che sto per registrare:" "Cyan"
Scrivi "  nome          $NomeAttivita"
Scrivi "  programma     $Pythonw"
Scrivi "  argomenti     monitor_arena.py once"
Scrivi "  cartella      $Cartella"
Scrivi "  quando        all'accesso a Windows, poi ogni $Minuti minuti"
Scrivi "  finestra      nessuna (pythonw non apre console)"
Scrivi ""

# --- creazione ------------------------------------------------------------ #

$azione = New-ScheduledTaskAction -Execute $Pythonw `
    -Argument "monitor_arena.py once" -WorkingDirectory $Cartella

# Trigger all'accesso, con ripetizione presa da un trigger "una volta":
# e' il modo che Windows accetta per ripetere all'infinito.
$trigger = New-ScheduledTaskTrigger -AtLogOn
$modello = New-ScheduledTaskTrigger -Once -At (Get-Date) `
    -RepetitionInterval (New-TimeSpan -Minutes $Minuti) `
    -RepetitionDuration (New-TimeSpan -Days 365)
$trigger.Repetition = $modello.Repetition

$impostazioni = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -MultipleInstances IgnoreNew `
    -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 5)

Register-ScheduledTask -TaskName $NomeAttivita -Action $azione -Trigger $trigger `
    -Settings $impostazioni -Force `
    -Description "Controlla i posti liberi in platea per Il Lago dei Cigni e avvisa su Telegram. Gira solo a PC acceso." | Out-Null

Scrivi "Attivita' registrata." "Green"
Scrivi ""

if (-not $telegramOk) {
    Scrivi "ATTENZIONE: in config.json mancano bot_token o chat_id." "Yellow"
    Scrivi "Il monitor girera' ma non potra' avvisarti: lancia '1 - Configura Telegram.bat'." "Yellow"
    Scrivi ""
}

Scrivi "Faccio partire subito un controllo di verifica..." "Cyan"
Start-ScheduledTask -TaskName $NomeAttivita
Start-Sleep -Seconds 45

$info = Get-ScheduledTaskInfo -TaskName $NomeAttivita
Scrivi ""
Scrivi "  ultimo avvio      $($info.LastRunTime)"
Scrivi "  esito             $($info.LastTaskResult)  (0 = tutto bene)"
Scrivi "  prossimo avvio    $($info.NextRunTime)"

$log = Join-Path $Cartella "monitor.log"
if (Test-Path $log) {
    Scrivi ""
    Scrivi "Ultime righe del log:" "Cyan"
    Get-Content $log -Tail 4 | ForEach-Object { Scrivi "  $_" }
}

Scrivi ""
Scrivi "Fatto. Da ora controlla ogni $Minuti minuti, ma solo mentre il PC e' acceso." "Green"
Scrivi "Per fermarlo:  .\Crea attivita pianificata.ps1 -Rimuovi" "Gray"
