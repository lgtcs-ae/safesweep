# SafeSweep - Free Safe Duplicate File Cleaner for Mac

**Clean duplicate files without fear.**

SafeSweep is a free, local-first duplicate file cleaner for Mac that helps you scan folders safely, review duplicate file candidates, and move approved files to a recoverable Vault.

Nothing is deleted automatically.
Your files stay on your computer.
You review everything before cleanup.

> Free at this moment while SafeSweep is in early beta.

## Why SafeSweep?

Most duplicate file cleaners feel risky.

SafeSweep is designed for people who want to clean files safely without accidentally deleting something important.

With SafeSweep, you can:

- Find duplicate files on your Mac.
- Review duplicate file groups before taking action.
- Move approved files to a recoverable Vault.
- Restore files before permanent cleanup.
- Scan folders locally without uploading files to the cloud.
- Clean Downloads, iPhone backups, WhatsApp media, photos, videos, documents, and external drives.

## SafeSweep Is Different

SafeSweep is not a delete-first cleaner. It is a review-first file cleanup app.

### Local-First Scanning

SafeSweep scans selected folders on your computer. Your files are not uploaded to any cloud service.

### Review Before Cleanup

You see duplicate candidates before anything moves. You decide what to approve, ignore, or keep.

### Recoverable Vault

Approved files move to the SafeSweep Vault first. You can restore them before permanent deletion.

### No Surprise Deletion

SafeSweep does not automatically delete files. Permanent cleanup only happens after your confirmation.

## Run

Clone the source:

```bash
git clone https://github.com/lgtcs-ae/safesweep.git
cd safesweep
```

Launch the local browser app:

```bash
python3 safesweep.py launch
```

This starts the local backend at:

```text
http://127.0.0.1:8765
```

To avoid opening a browser window:

```bash
python3 safesweep.py launch --no-browser
```

Run a direct CLI scan:

```bash
python3 safesweep.py scan --folders ~/Downloads ~/Desktop
```

Approve and move confirmed duplicates from a completed scan:

```bash
python3 safesweep.py approve-confirmed --scan ~/SafeSweep_Review_<timestamp>
python3 safesweep.py move-approved --scan ~/SafeSweep_Review_<timestamp>
```

Restore moved files:

```bash
python3 safesweep.py restore --scan ~/SafeSweep_Review_<timestamp>
```

## Build macOS DMG

SafeSweep can be packaged as an unsigned macOS app and DMG for local testing:

```bash
python3 -m pip install pyinstaller pillow
bash packaging/macos/build_dmg.sh
```

Outputs:

```text
dist/SafeSweep.app
release/macos/SafeSweep-macOS.dmg
```

See `packaging/macos/README.md` for notes on smoke testing, signing, and notarization.

### macOS Preview Warning

The current DMG is an early tester preview and is not yet Apple Developer ID
signed or notarized. macOS may block it with an Apple verification warning.

Advanced testers can manually allow the installed app with:

```bash
xattr -dr com.apple.quarantine /Applications/SafeSweep.app
```

The proper public distribution path is Apple Developer ID signing and
notarization.

## Current Scope

Implemented:

- Local backend bound to `127.0.0.1`.
- Polished Home, Scan, and Results browser UI.
- Scan page with default folder suggestions, folder picker, live progress, and navigation-safe background scan resume.
- Safe recursive scanning.
- Default scan folders: `~/Downloads`, `~/Desktop`.
- Default ignore rules for system folders, user Library, Trash, noisy dev folders, hidden folders, Photos libraries, and app packages.
- File metadata collection.
- Name normalization.
- Chunked SHA-256 hashing for same-size candidate files.
- Hash safety metadata for missing files, permission errors, deleted files, and files changed during hashing.
- Background UI scan jobs with polling progress.
- Confirmed duplicate detection using same SHA-256 and same size.
- Very likely duplicate detection only when files have the same size, same extension, similar normalized names, and no available hash disagreement.
- Different-size similar names are ignored by default to reduce false positives.
- Newest-file Actual selection.
- Permission and unreadable item logging.
- SafeSweep review folder creation.
- Empty restore map creation.
- JSON, CSV, and standalone HTML candidate reports.
- Results page with search, filters, sorting, approvals, move-approved, restore, and Permanent Sweep controls.
- Restore map entries for every moved file.
- Stricter default results: files with different sizes are not shown as duplicate groups.

Not implemented yet:

- Native macOS UI.
- Visual file previews.
- Perceptual image/PDF similarity.
- Scheduled scans.

## Safety Guarantees

- Scans never move files.
- Only approved duplicate candidates can move.
- Actual files are never moved.
- Moved duplicates go only into `03_SafeSweep_Vault`.
- Permanent Sweep applies only to moved Vault files and requires explicit confirmation.
- Restore never overwrites existing files.
- System folders are skipped by default.
- Hidden folders are skipped unless explicitly enabled.
- Files are never classified as confirmed duplicates by name alone.
- Files changed during hashing are not used for duplicate confirmation.
- Scan errors are logged instead of crashing the scan.
- Restore maps and logs are created for every scan folder.

## Review Folder

Each scan creates a timestamped folder:

```text
~/SafeSweep_Review_<timestamp>/
    approval_state.json

    01_Reports/
        safesweep_report.html
        safesweep_report.csv
        safesweep_report.json
        safesweep_scan_summary.json
        safesweep_scan_records.json
    02_Actual/
        aliases_to_kept_files/
        actual_files_index.csv
    03_SafeSweep_Vault/
        confirmed_duplicates/
        likely_duplicates/
        possible_duplicates/
    04_Logs/
        scan_log.txt
        actions_log.txt
        errors_log.txt
    05_Restore_Map/
        restore_map.json
```

The vault folders are used only when approved duplicate candidates are moved.

## Best For

- Cleaning duplicate files on Mac.
- Finding duplicate photos and videos.
- Cleaning Downloads folders.
- Cleaning iPhone backup folders.
- Cleaning WhatsApp media folders.
- Cleaning external hard drives.
- Reviewing duplicate documents.
- Safely freeing up disk space.
- Organizing messy folders.

## Development

The current environment can run SafeSweep without installing packages. If you want the optional Jinja2 renderer path:

```bash
python3 -m pip install -r requirements.txt
```

Run tests:

```bash
python3 -m unittest discover -s tests
```

## Product Promise

SafeSweep follows one simple rule:

> Review first. Clean safely.

That means:

- No automatic deletion.
- No cloud upload.
- No hidden cleanup.
- No risky bulk removal.
- No permanent delete without confirmation.

## FAQ

### Is SafeSweep free?

Yes. SafeSweep is free at this moment while it is in early beta.

### Does SafeSweep delete files automatically?

No. SafeSweep never deletes files automatically.

### Does SafeSweep upload my files?

No. SafeSweep is designed as a local-first app. Your selected folders are scanned on your computer.

### What is the Vault?

The Vault is a recoverable cleanup area. Approved files move there first so you can restore them before permanent deletion.

### Is SafeSweep for Mac?

Yes. SafeSweep is currently focused on Mac.

## Tagline

**SafeSweep - Review first. Clean safely.**
