# PC Info Tool 2.0.0 — Release Checklist

## Build
- [ ] Extract into a new folder.
- [ ] Run `build_exe.bat` on Windows.
- [ ] Confirm the build completes successfully.
- [ ] Confirm `dist\\PCInfoTool2\\PCInfoTool2.exe` exists.
- [ ] Distribute the entire `dist\\PCInfoTool2` folder, not the EXE alone.

## Launch and compatibility
- [ ] Launch on the build machine.
- [ ] Test on another Windows machine without Python installed.
- [ ] Confirm icon and file/product version are 2.0.0.

## Functional tests
- [ ] Dashboard and hardware information.
- [ ] Live CPU/RAM/disk/network monitoring.
- [ ] Diagnostics.
- [ ] CPU, memory, and disk benchmarks.
- [ ] Benchmark history after restart.
- [ ] HTML and JSON reports.
- [ ] CSV export.
- [ ] Dark and light themes.
- [ ] No unexpected startup errors.

## Release
- [ ] Record Windows versions and test hardware.
- [ ] Fix release-blocking issues.
- [ ] Archive the final build and checksum.
