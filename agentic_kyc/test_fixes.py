#!/usr/bin/env python3
"""
Test script to validate KYC agent fixes.
Tests:
1. PAN normalization and matching
2. Compliance findings accuracy
3. Data flow through agents
"""

from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from agents.compliance_agent import exact_score, mask_aadhaar, normalize_pan, screen_file
from agents.document_agent import merge_document_data


def test_merge_document_data():
    """Test document merge function preserves PAN data."""
    print("\n" + "=" * 60)
    print("TEST: Document merge function preserves PAN data")
    print("=" * 60)
    
    pan_data = {
        "name": "S P RANJITH",
        "dob": "1999-08-16",
        "pan_number": "DHRPR8630C",
        "aadhaar_number": "",
        "address": "",
        "extraction_confidence": 0,
        "evidence": ["Name: S P RANJITH", "PAN: DHRPR8630C"],
    }
    
    aadhaar_data = {
        "name": "Ranjith S P",
        "dob": "1999-08-16",
        "pan_number": "",
        "aadhaar_number": "XXXX-XXXX-0061",
        "address": "C/O Padmapriya S, 31FJ, WARD 4, CHELLANDIYAMMAN KOVIL STREET",
        "extraction_confidence": 0,
        "evidence": ["Name from top", "DOB below name", "Aadhaar number", "Address at bottom"],
    }
    
    merged = merge_document_data(pan_data, aadhaar_data)
    
    print(f"Input PAN data: {pan_data['pan_number']}")
    print(f"Input Aadhaar data: {aadhaar_data['aadhaar_number']}")
    print(f"Merged PAN: {merged['pan_number']}")
    print(f"Merged Aadhaar: {merged['aadhaar_number']}")
    print(f"Merged Name: {merged['name']}")
    print(f"Merged DOB: {merged['dob']}")
    
    tests_pass = 0
    tests_total = 4
    
    if merged['pan_number'] == "DHRPR8630C":
        print("✓ PAN number correctly merged from PAN data")
        tests_pass += 1
    else:
        print(f"✗ PAN number merge failed: got '{merged['pan_number']}'")
    
    if merged['aadhaar_number'] == "XXXX-XXXX-0061":
        print("✓ Aadhaar number correctly merged from Aadhaar data")
        tests_pass += 1
    else:
        print(f"✗ Aadhaar merge failed: got '{merged['aadhaar_number']}'")
    
    if merged['name'] == "S P RANJITH":
        print("✓ Name correctly prioritized from PAN data")
        tests_pass += 1
    else:
        print(f"✗ Name merge failed: got '{merged['name']}'")
    
    if merged['dob'] == "1999-08-16":
        print("✓ DOB correctly merged")
        tests_pass += 1
    else:
        print(f"✗ DOB merge failed: got '{merged['dob']}'")
    
    print(f"\nMerge tests: {tests_pass}/{tests_total} pass")


def test_exact_score():
    """Test PAN normalization and exact scoring."""
    print("=" * 60)
    print("TEST: exact_score() with PAN normalization")
    print("=" * 60)
    
    test_cases = [
        ("AORPR2481F", "AORPR2481F", 100, "Exact match"),
        ("AORPR2481F", "aorpr2481f", 100, "Case normalization"),
        ("AORPR2481F", "AOR PR2481F", 100, "Space removal"),
        ("AORPR2481F", "aor pr 2481 f", 100, "Case + spaces"),
        ("AORPR2481F", "DIFFERENT1234F", 0, "No match"),
        ("", "AORPR2481F", 0, "Empty left"),
    ]
    
    for left, right, expected, desc in test_cases:
        result = exact_score(left, right)
        status = "✓" if result == expected else "✗"
        print(f"{status} {desc:30} | {left:15} vs {right:15} | Result: {result} (Expected: {expected})")


def test_mask_aadhaar():
    """Test Aadhaar masking consistency."""
    print("\n" + "=" * 60)
    print("TEST: mask_aadhaar() consistency")
    print("=" * 60)
    
    test_cases = [
        ("4821 6630 9182", "XXXX-XXXX-9182"),
        ("4821663091 82", "XXXX-XXXX-9182"),
        ("482166309182", "XXXX-XXXX-9182"),
        ("XXXX-XXXX-9182", "XXXX-XXXX-9182"),
    ]
    
    for input_val, expected in test_cases:
        result = mask_aadhaar(input_val)
        status = "✓" if result == expected else "✗"
        print(f"{status} {input_val:20} -> {result:15} (Expected: {expected})")


def test_compliance_screening():
    """Test compliance screening with sample data."""
    print("\n" + "=" * 60)
    print("TEST: Compliance screening with real data")
    print("=" * 60)
    
    # Test with sample data that should NOT match
    sample_data = {
        "name": "Ananya Rao",
        "dob": "1991-07-18",
        "pan_number": "AORPR2481F",
        "aadhaar_number": "4821 6630 9182",
        "address": "42 Lake View Road, Indiranagar, Bengaluru, Karnataka 560038",
    }
    
    watchlist_path = ROOT_DIR / "data" / "watchlist.csv"
    blacklist_path = ROOT_DIR / "data" / "blacklist.csv"
    
    watchlist_findings = screen_file(watchlist_path, "watchlist", sample_data)
    blacklist_findings = screen_file(blacklist_path, "blacklist", sample_data)
    
    print(f"Sample Data: {sample_data['name']} | PAN: {sample_data['pan_number']}")
    print(f"Watchlist findings: {len(watchlist_findings)}")
    print(f"Blacklist findings: {len(blacklist_findings)}")
    
    if len(watchlist_findings) == 0:
        print("✓ Correctly no watchlist match for Ananya Rao")
    else:
        print(f"✗ Unexpected watchlist findings: {watchlist_findings}")
    
    if len(blacklist_findings) == 0:
        print("✓ Correctly no blacklist match for Ananya Rao")
    else:
        print(f"✗ Unexpected blacklist findings: {blacklist_findings}")
    
    # Test with data that SHOULD match
    print("\n" + "-" * 60)
    test_data_watchlist = {
        "name": "Rajesh Malhotra",
        "dob": "1980-04-14",
        "pan_number": "ABCPM1234F",
        "aadhaar_number": "XXXX-XXXX-1122",
    }
    
    watchlist_match = screen_file(watchlist_path, "watchlist", test_data_watchlist)
    print(f"\nTest Data: {test_data_watchlist['name']} | PAN: {test_data_watchlist['pan_number']}")
    print(f"Watchlist findings: {len(watchlist_match)}")
    
    if len(watchlist_match) > 0:
        print("✓ Correctly matched watchlist entry")
        for finding in watchlist_match:
            print(f"  - Source: {finding.get('source')}")
            print(f"  - Reason: {finding.get('reason')}")
            print(f"  - Evidence: {finding.get('evidence')}")
    else:
        print("✗ Failed to match watchlist entry")


def test_pan_extraction():
    """Test PAN extraction from sample documents."""
    print("\n" + "=" * 60)
    print("TEST: PAN extraction from sample documents")
    print("=" * 60)
    
    sample_pan_path = ROOT_DIR / "data" / "sample_documents" / "sample_pan.txt"
    
    if sample_pan_path.exists():
        content = sample_pan_path.read_text()
        print(f"Sample PAN document content:\n{content}\n")
        
        # Check if PAN is extractable
        import re
        pan_pattern = r"\b([A-Z]{5}[0-9]{4}[A-Z])\b"
        matches = re.findall(pan_pattern, content)
        
        if matches:
            print(f"✓ Found PAN number: {matches[0]}")
            for match in matches:
                print(f"  - {match}")
        else:
            print("✗ Failed to extract PAN number")
    else:
        print(f"✗ Sample PAN file not found: {sample_pan_path}")


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("KYC AGENT FIXES VALIDATION TEST SUITE")
    print("=" * 60 + "\n")
    
    test_exact_score()
    test_mask_aadhaar()
    test_merge_document_data()
    test_compliance_screening()
    test_pan_extraction()
    
    print("\n" + "=" * 60)
    print("TEST SUITE COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()
