# PyQt5 FaradayExplorer - Frequency Loading Test Guide

## Test Environment Setup

### Prerequisites
```bash
conda activate faraday_explorer
cd /home/amani/FaradayExplorer
python3 faraday_explorer.py  # Verify app runs normally
```

### Test Files

Create test frequency files:

```bash
# CSV format
echo "1.4,1.5,1.6,1.7,1.8" > test_frequencies.csv

# Newline format
cat > test_frequencies.txt <<EOF
1.4
1.5
1.6
1.7
1.8
EOF

# Mixed format
cat > test_frequencies_mixed.txt <<EOF
1.4,1.5
1.6
1.7,1.8
EOF
```

---

## Test 1: File Menu Items Visible

**Objective:** Verify that new menu items appear in File menu

**Steps:**
1. Launch app: `python3 faraday_explorer.py`
2. Select dataset (or close file picker to continue)
3. Click menu: File
4. Scroll down to find "Load Frequency File…"
5. Verify "Enter Frequencies Manually…" is below it

**Expected Result:**
- Both menu items visible in File menu
- Located after "Workspaces" section
- Located before "Quit"

**Success Criteria:** ✓ Menu items appear

---

## Test 2: Load Frequency File - CSV Format

**Objective:** Test loading frequencies from CSV file

**Steps:**
1. Create test file: `echo "1.4,1.5,1.6,1.7,1.8" > test_freq.csv`
2. Launch app and load FDF dataset
3. Click File → Load Frequency File…
4. Select `test_freq.csv`
5. Verify preview shows: "1.4,1.5,1.6,1.7,1.8"
6. Click "Load"

**Expected Result:**
- Dialog opens
- File preview displays correctly
- Dialog closes
- Status bar shows: "Loaded 5 frequencies. RMSF recalculated."
- FDF plot updates with new RMSF (grey shading)

**Success Criteria:** ✓ Frequencies loaded, RMSF updated

---

## Test 3: Load Frequency File - Newline Format

**Objective:** Test loading frequencies from newline-separated file

**Steps:**
1. Create test file:
   ```bash
   cat > test_freq.txt <<EOF
   1.4
   1.5
   1.6
   1.7
   1.8
   EOF
   ```
2. Click File → Load Frequency File…
3. Select `test_freq.txt`
4. Verify preview shows line-by-line frequencies
5. Click "Load"

**Expected Result:**
- Same as Test 2
- Parser correctly handles newline-separated format

**Success Criteria:** ✓ Newline-separated frequencies loaded

---

## Test 4: Load Frequency File - Mixed Format

**Objective:** Test loading mixed comma/newline format

**Steps:**
1. Create test file:
   ```bash
   cat > test_freq_mixed.txt <<EOF
   1.4,1.5
   1.6
   1.7,1.8
   EOF
   ```
2. Click File → Load Frequency File…
3. Select `test_freq_mixed.txt`
4. Click "Load"

**Expected Result:**
- Status shows: "Loaded 5 frequencies"
- All 5 values parsed correctly regardless of separator

**Success Criteria:** ✓ Mixed format parsed correctly

---

## Test 5: Load Frequency File - Empty File

**Objective:** Test error handling for empty file

**Steps:**
1. Create empty file: `touch empty.txt`
2. Click File → Load Frequency File…
3. Select `empty.txt`
4. Click "Load"

**Expected Result:**
- Dialog stays open
- Error message: "No frequencies found in file."

**Success Criteria:** ✓ Error handled gracefully

---

## Test 6: Load Frequency File - Invalid Format

**Objective:** Test error handling for invalid data

**Steps:**
1. Create invalid file:
   ```bash
   echo "abc, not numbers, xyz" > invalid.txt
   ```
2. Click File → Load Frequency File…
3. Select `invalid.txt`
4. Click "Load"

**Expected Result:**
- Error dialog shows: "Failed to parse file: [error details]"
- Dialog closes without loading

**Success Criteria:** ✓ Invalid file rejected

---

## Test 7: Enter Frequencies Manually - Comma Separated

**Objective:** Test manual entry with comma-separated input

**Steps:**
1. Click File → Enter Frequencies Manually…
2. Enter: `1.4, 1.5, 1.6`
3. Verify status shows: "Parsed 3 frequencies"
4. Click "Load"

**Expected Result:**
- Dialog opens with text input
- Status shows count as user types
- Dialog closes after clicking Load
- Status bar shows: "Loaded 3 frequencies. RMSF recalculated."

**Success Criteria:** ✓ Manual entry works

---

## Test 8: Enter Frequencies Manually - Newline Separated

**Objective:** Test manual entry with newline-separated input

**Steps:**
1. Click File → Enter Frequencies Manually…
2. Paste:
   ```
   1.4
   1.5
   1.6
   ```
3. Click "Load"

**Expected Result:**
- All 3 frequencies parsed
- Status bar confirmation

**Success Criteria:** ✓ Newline parsing works

---

## Test 9: Enter Frequencies Manually - Invalid Input

**Objective:** Test error handling for invalid manual entry

**Steps:**
1. Click File → Enter Frequencies Manually…
2. Enter: `1.4, abc, 1.6`
3. Click "Load"

**Expected Result:**
- Error message: "Invalid number: 'abc'"
- Dialog stays open
- Can edit and retry

**Success Criteria:** ✓ Invalid input rejected

---

## Test 10: Enter Frequencies Manually - Empty Input

**Objective:** Test "Load" button disabled when empty

**Steps:**
1. Click File → Enter Frequencies Manually…
2. Verify "Load" button is disabled (greyed out)
3. Type something and delete it
4. Verify button becomes disabled again

**Expected Result:**
- Button state matches input validity
- Can only click when text is present

**Success Criteria:** ✓ Button state correct

---

## Test 11: RMSF Recalculation

**Objective:** Verify RMSF is properly recalculated after frequency update

**Steps:**
1. Load initial dataset (records RMSF shape)
2. Click File → Load Frequency File…
3. Load very different frequencies (e.g., 800 MHz, 1400 MHz, 1900 MHz)
4. Observe FDF plot

**Expected Result:**
- Grey RMSF shading changes shape
- RMSF peak (1.0) remains at RM = 0
- RMSF width changes inversely with frequency bandwidth

**Success Criteria:** ✓ RMSF recalculated correctly

---

## Test 12: Command-Line .mod File Argument

**Objective:** Test command-line argument handling for .mod files

**Steps:**
1. Create dummy .mod file: `touch test.mod`
2. Launch: `python3 faraday_explorer.py test.mod`
3. Verify: LaunchDialog appears (GUI mode, not error)
4. Check console output for: "File association: .mod file requested"

**Expected Result:**
- App launches normally
- File picker dialog shown
- Can select FDF/frequency files as usual
- No error about .mod file

**Success Criteria:** ✓ .mod file detected, app continues

---

## Test 13: Workspace Preservation on .mod File Open

**Objective:** Verify workspace state not cleared by .mod file

**Steps:**
1. Load a dataset normally
2. Adjust: theme (light/dark), zoom level, panel layout
3. Launch in new window: `python3 faraday_explorer.py test.mod`
4. In original window: File → Load Frequency File… (changes frequencies)
5. Verify: All adjustments still present

**Expected Result:**
- Theme unchanged
- Panel layout unchanged
- Zoom/pan state unchanged
- Only frequencies and RMSF updated

**Success Criteria:** ✓ Workspace preserved

---

## Test 14: Linux File Association Setup

**Objective:** Test file association on Linux file manager

**Prerequisites:**
```bash
# Install MIME type
xdg-mime install /home/amani/FaradayExplorer/faraday-model.xml

# Update desktop database
update-desktop-database ~/.local/share/applications
```

**Steps:**
1. Create test file: `touch ~/test.mod`
2. Open file manager
3. Right-click `test.mod`
4. Verify "Open with Faraday Explorer" option appears
5. Click it

**Expected Result:**
- App launches
- File picker dialog shown
- Console shows: "File association: .mod file requested"

**Success Criteria:** ✓ File association works

---

## Test 15: Frequency Update in Real Data

**Objective:** Test frequency change with real FDF data loaded

**Steps:**
1. Load a dataset with real FDF data (from aperture)
2. Observe current FDF plot
3. File → Load Frequency File…
4. Load different frequencies (e.g., 10 frequencies instead of 9)
5. Observe FDF plot updates

**Expected Result:**
- Plot updates immediately
- RMSF width changes to match new frequencies
- Real data FDF plot shape may change (fewer/more channels)
- No crash or error

**Success Criteria:** ✓ Works with real data

---

## Test 16: Status Bar Feedback

**Objective:** Verify status messages for user feedback

**Test Steps:**
1. Load frequency file → Check status: "Loaded X frequencies..."
2. Manual entry → Check status: "Loaded X frequencies..."
3. Open file dialog → Cancel → Check status returns to previous

**Expected Result:**
- Status bar shows confirmation after load
- Status reflects number of frequencies loaded
- Helpful messages guide user

**Success Criteria:** ✓ Status feedback clear

---

## Test 17: Multiple Consecutive Loads

**Objective:** Test repeated frequency loading

**Steps:**
1. File → Load Frequency File… → Load 5 frequencies
2. File → Load Frequency File… → Load 9 frequencies
3. File → Enter Frequencies Manually… → Load 7 frequencies
4. Observe each update applies correctly

**Expected Result:**
- Each load completely replaces previous frequencies
- No accumulation or mixing of data
- RMSF recalculates each time
- Status shows correct count

**Success Criteria:** ✓ Multiple loads work correctly

---

## Test 18: Large Frequency File

**Objective:** Test performance with many frequencies

**Steps:**
1. Create file with 1000 frequencies: 
   ```bash
   python3 -c "print('\n'.join(map(str, np.linspace(1.0, 2.0, 1000))))" > large_freq.txt
   ```
2. File → Load Frequency File…
3. Select large file
4. Click "Load"
5. Time the operation

**Expected Result:**
- File loads within 1-2 seconds
- RMSF recalculates smoothly
- No lag or freezing
- Status shows: "Loaded 1000 frequencies..."

**Success Criteria:** ✓ Handles large files efficiently

---

## Test 19: Frequency File with Comments

**Objective:** Test robustness with commented files

**Steps:**
1. Create file with comments:
   ```bash
   cat > freq_comments.txt <<EOF
   # My frequency file
   1.4
   # Main band
   1.5
   1.6
   EOF
   ```
2. File → Load Frequency File…
3. Try to load

**Expected Result:**
- Either:
  a) Loads 3 frequencies correctly (numpy ignores comments), OR
  b) Shows error (depends on numpy behavior)
- Either way, no crash

**Success Criteria:** ✓ Handles edge case

---

## Test 20: Cancel Operations

**Objective:** Verify cancel buttons work

**Steps:**
1. File → Load Frequency File…
2. Click "Cancel"
3. Verify dialog closes, no change to frequencies

4. File → Enter Frequencies Manually…
5. Type something
6. Click "Cancel"
7. Verify dialog closes, no change applied

**Expected Result:**
- Cancel buttons work
- No state changed when cancelled
- App continues normally

**Success Criteria:** ✓ Cancel operations work

---

## Integration Test Summary

### Quick Full Test (5 minutes)

1. ✓ Launch app
2. ✓ Load dataset
3. ✓ File → Load Frequency File → CSV file
4. ✓ Verify RMSF updates
5. ✓ File → Enter Frequencies Manually → Type "1.4, 1.5, 1.6"
6. ✓ Verify status message

### Full Test Suite (20 minutes)

Run all 20 tests listed above in sequence.

### Linux File Association Test (5 minutes)

1. ✓ Install MIME type
2. ✓ Create .mod file
3. ✓ Double-click in file manager
4. ✓ Verify app opens

---

## Troubleshooting

### Issue: Menu items not appearing
**Solution:** Restart app after code changes

### Issue: "No such file" error
**Solution:** Verify file path is absolute or relative to correct directory

### Issue: File association not working
**Solution:** Run: `update-desktop-database ~/.local/share/applications`

### Issue: RMSF doesn't update
**Solution:** Check console for errors; verify frequencies are valid

### Issue: Dialog hangs
**Solution:** Check for large file; may take a few seconds to parse

---

## Success Criteria Summary

- [ ] Test 1: Menu items visible
- [ ] Test 2: CSV loading works
- [ ] Test 3: Newline loading works
- [ ] Test 4: Mixed format works
- [ ] Test 5: Empty file error handled
- [ ] Test 6: Invalid format error handled
- [ ] Test 7: Manual comma entry works
- [ ] Test 8: Manual newline entry works
- [ ] Test 9: Invalid manual input error handled
- [ ] Test 10: Empty input state correct
- [ ] Test 11: RMSF recalculated
- [ ] Test 12: .mod file arg detected
- [ ] Test 13: Workspace preserved
- [ ] Test 14: Linux file association works
- [ ] Test 15: Works with real data
- [ ] Test 16: Status feedback clear
- [ ] Test 17: Multiple loads work
- [ ] Test 18: Large files handled
- [ ] Test 19: Edge cases handled
- [ ] Test 20: Cancel operations work

**All tests pass: ✓ Implementation complete**
