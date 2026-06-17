# How to Export Discord Messages (DiscordChatExporter)

## One-time setup

1. Download `DiscordChatExporter.Cli.win-x64.zip` from github.com/Tyrrrz/DiscordChatExporter/releases
2. Unzip to `C:\Users\jakers\Downloads\DCE\`

## Get your user token (do this each time token expires)

1. Quit Discord completely (system tray bottom-right `^` → right-click Discord → Quit)
2. The settings.json already has DevTools enabled at `%APPDATA%\discord\settings.json`
3. Reopen Discord desktop app
4. Press `Ctrl+Shift+I` → Console tab
5. Paste:
```js
let m;webpackChunkdiscord_app.push([[Math.random()],{},e=>{for(let i in e.c){let x=e.c[i];if(x?.exports?.getToken){m=x;break}}}]);m&&console.log("Token:",m.exports.getToken());
```
6. Copy the token that prints (long string starting with letters/numbers)

## Export a channel

### Full export (all history from a date)
```powershell
& "$env:USERPROFILE\Downloads\DCE\DiscordChatExporter.Cli.exe" export -c CHANNEL_ID -t "YOUR_TOKEN" -f Json -o "$env:USERPROFILE\Downloads\grizzlies_export.json" --after "2024-01-01"
```

### Date range export (recommended — faster)
```powershell
& "$env:USERPROFILE\Downloads\DCE\DiscordChatExporter.Cli.exe" export -c CHANNEL_ID -t "YOUR_TOKEN" -f Json -o "$env:USERPROFILE\Downloads\grizzlies_export.json" --after "2026-05-01" --before "2026-06-01"
```

## Known channel IDs

| Trader | Channel ID |
|--------|-----------|
| Grizzlies | 1025803258691862678 |

Server ID: 697936741117460640

## Import into the pipeline

Once exported, run:
```
cd C:\Users\jakers\Desktop\ProjectDolph2.0
python ingestion/from_discord_export.py C:\Users\jakers\Downloads\grizzlies_export.json Grizzlies
```

Then re-profile and run:
```
python main.py Grizzlies
python dev.py --paper Grizzlies --save
```

## Notes

- The `--after` / `--before` flags take dates in `YYYY-MM-DD` format
- Export stays at 0% for a while on large date ranges — that's normal, just wait
- If token is invalid, repeat the token extraction steps above (tokens expire when you change your password)
- Run exports in monthly chunks if the channel has a lot of history
