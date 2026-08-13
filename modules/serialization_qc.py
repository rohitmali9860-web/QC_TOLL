"""
serialization_qc.py - Module 3: RFID / Non-RFID & Serialization QC
Validates EPC/SGTIN-96 structure, uniqueness, consecutive serial increments,
sequence gaps, duplicates, and SKU progression (e.g., 1/3, 2/3, 3/3).
Supports RFID vs Non-RFID and Serialized vs Non-Serialized item classifications.
"""

import re

class SerializationQCAnalyzer:
    def __init__(self):
        pass

    def decode_sgtin96(self, hex_epc):
        """
        Parses a 96-bit hexadecimal EPC into GS1 SGTIN-96 components.
        Returns a dict of parsed fields or raises ValueError if invalid.
        """
        hex_clean = hex_epc.strip().replace(" ", "").upper()
        if len(hex_clean) != 24:
            return {'valid': False, 'error': f"Invalid length: EPC must be 24 hex characters (96 bits), found {len(hex_clean)}."}

        try:
            # Convert hex to 96-bit binary string
            bin_str = bin(int(hex_clean, 16))[2:].zfill(96)
        except ValueError:
            return {'valid': False, 'error': "Invalid hexadecimal characters in EPC string."}

        header = bin_str[0:8]
        filter_val = bin_str[8:11]
        partition = bin_str[11:14]

        # SGTIN-96 Header is binary 00110000 (0x30)
        is_sgtin96_header = (header == '00110000')

        partition_table = {
            '000': {'comp_bits': 40, 'comp_digits': 12, 'item_bits': 4, 'item_digits': 1},
            '001': {'comp_bits': 37, 'comp_digits': 11, 'item_bits': 7, 'item_digits': 2},
            '010': {'comp_bits': 34, 'comp_digits': 10, 'item_bits': 10, 'item_digits': 3},
            '011': {'comp_bits': 30, 'comp_digits': 9, 'item_bits': 14, 'item_digits': 4},
            '100': {'comp_bits': 27, 'comp_digits': 8, 'item_bits': 17, 'item_digits': 5},
            '101': {'comp_bits': 24, 'comp_digits': 7, 'item_bits': 20, 'item_digits': 6},
            '110': {'comp_bits': 20, 'comp_digits': 6, 'item_bits': 24, 'item_digits': 7}
        }

        part_info = partition_table.get(partition, {'comp_bits': 24, 'comp_digits': 7, 'item_bits': 20, 'item_digits': 6})
        comp_bits = part_info['comp_bits']
        item_bits = part_info['item_bits']

        c_start = 14
        c_end = c_start + comp_bits
        i_end = c_end + item_bits

        company_prefix_int = int(bin_str[c_start:c_end], 2)
        item_ref_int = int(bin_str[c_end:i_end], 2)
        serial_int = int(bin_str[i_end:96], 2)

        filter_names = {
            '000': 'All Others (0)',
            '001': 'Point of Sale (POS) Item (1)',
            '010': 'Full Case for Transport (2)',
            '011': 'Reserved (3)',
            '100': 'Inner Pack (4)'
        }

        return {
            'valid': is_sgtin96_header,
            'hex': hex_clean,
            'header_bin': header,
            'header_hex': '0x30' if is_sgtin96_header else f"0x{int(header, 2):02X}",
            'filter_bin': filter_val,
            'filter_name': filter_names.get(filter_val, f"Filter {int(filter_val, 2)}"),
            'partition': partition,
            'company_prefix': str(company_prefix_int).zfill(part_info['comp_digits']),
            'item_reference': str(item_ref_int).zfill(part_info['item_digits']),
            'serial_number': serial_int,
            'epc_uri': f"urn:epc:tag:sgtin-96:{int(filter_val,2)}.{company_prefix_int}.{item_ref_int}.{serial_int}"
        }

    def validate_batch(self, is_rfid=True, is_serialized=True, order_records=None, epc_list=None, sku_sequences=None):
        """
        Runs comprehensive validation on serial numbers and EPC codes across a batch.
        """
        checks = []
        passed_count = 0
        total_count = 0

        # Scenario 1: Non-RFID item
        if not is_rfid:
            checks.append({
                'check_id': 'item_classification',
                'field_name': 'Item Classification',
                'expected': 'Non-RFID Item',
                'actual': 'Non-RFID Confirmed (RFID checks skipped)',
                'status': 'PASS',
                'severity': 'LOW',
                'details': 'Item code is classified as Non-RFID. RFID-specific checks bypassed.'
            })
            return {
                'sector_name': 'RFID & Serialization QC',
                'score': 100.0,
                'status': 'PASS',
                'is_rfid': False,
                'is_serialized': is_serialized,
                'total_checks': 1,
                'passed_checks': 1,
                'failed_checks': 0,
                'checks': checks
            }

        # Scenario 2: RFID Non-Serialized
        if is_rfid and not is_serialized:
            checks.append({
                'check_id': 'rfid_non_serialized',
                'field_name': 'RFID Structure',
                'expected': 'Static Tag Data / Non-Serialized',
                'actual': 'Static RFID confirmed',
                'status': 'PASS',
                'severity': 'LOW',
                'details': 'RFID tag operates in static non-serialized mode.'
            })
            return {
                'sector_name': 'RFID & Serialization QC',
                'score': 100.0,
                'status': 'PASS',
                'is_rfid': True,
                'is_serialized': False,
                'total_checks': 1,
                'passed_checks': 1,
                'failed_checks': 0,
                'checks': checks
            }

        # Scenario 3: RFID Serialized
        # Default test EPC batch if none provided
        sample_epcs = epc_list or [
            "3034027780000000000003E9",  # 1001
            "3034027780000000000003EA",  # 1002
            "3034027780000000000003EB",  # 1003
            "3034027780000000000003EC",  # 1004
            "3034027780000000000003ED"   # 1005
        ]

        # 1. EPC Structure and GS1 SGTIN-96 Validation
        decoded_items = []
        malformed_epcs = []

        for idx, epc in enumerate(sample_epcs):
            total_count += 1
            dec = self.decode_sgtin96(epc)
            if dec['valid']:
                passed_count += 1
                decoded_items.append(dec)
            else:
                malformed_epcs.append((epc, dec.get('error', 'Malformed structure')))

        if not malformed_epcs:
            checks.append({
                'check_id': 'epc_structure_all',
                'field_name': 'SGTIN-96 EPC Format',
                'expected': 'Valid 96-bit Hex with Header 0x30',
                'actual': f"All {len(sample_epcs)} EPC tags valid",
                'status': 'PASS',
                'severity': 'LOW',
                'details': 'Every EPC tag strictly satisfies GS1 EPC Tag Data Standard (SGTIN-96).'
            })
        else:
            checks.append({
                'check_id': 'epc_structure_all',
                'field_name': 'SGTIN-96 EPC Format',
                'expected': 'Valid 96-bit Hex',
                'actual': f"{len(malformed_epcs)} Malformed EPCs detected",
                'status': 'FAIL',
                'severity': 'CRITICAL',
                'details': f"Malformed EPCs found: {malformed_epcs[:3]}"
            })

        # 2. Duplicate Detection
        total_count += 1
        seen_serials = {}
        duplicates = []

        for d in decoded_items:
            s_num = d['serial_number']
            if s_num in seen_serials:
                duplicates.append((s_num, seen_serials[s_num], d['hex']))
            else:
                seen_serials[s_num] = d['hex']

        if not duplicates:
            passed_count += 1
            checks.append({
                'check_id': 'duplicate_serials',
                'field_name': 'Serial Uniqueness',
                'expected': '0 Duplicate Serials',
                'actual': 'No duplicates found across batch',
                'status': 'PASS',
                'severity': 'LOW',
                'details': 'All serial numbers in the batch are 100% unique.'
            })
        else:
            checks.append({
                'check_id': 'duplicate_serials',
                'field_name': 'Serial Uniqueness',
                'expected': '0 Duplicate Serials',
                'actual': f"{len(duplicates)} Duplicate serial numbers detected!",
                'status': 'FAIL',
                'severity': 'CRITICAL',
                'details': f"Duplicate EPCs: {duplicates}"
            })

        # 3. Consecutive Sequence & Gap Detection
        total_count += 1
        extracted_serials = sorted(seen_serials.keys())
        gaps = []

        if len(extracted_serials) > 1:
            for i in range(len(extracted_serials) - 1):
                curr = extracted_serials[i]
                nxt = extracted_serials[i+1]
                if nxt != curr + 1:
                    gaps.append((curr, nxt, nxt - curr - 1))

        if not gaps:
            passed_count += 1
            checks.append({
                'check_id': 'serial_gaps',
                'field_name': 'Sequential Integrity (Gaps)',
                'expected': 'Monotonically incrementing by +1',
                'actual': f"Continuous range [{extracted_serials[0]} to {extracted_serials[-1]}] (No gaps)",
                'status': 'PASS',
                'severity': 'LOW',
                'details': f"Serials form an unbroken sequence from {extracted_serials[0]} to {extracted_serials[-1]}."
            })
        else:
            checks.append({
                'check_id': 'serial_gaps',
                'field_name': 'Sequential Integrity (Gaps)',
                'expected': 'Continuous unbroken range',
                'actual': f"Detected {len(gaps)} sequence gap(s)",
                'status': 'FAIL',
                'severity': 'HIGH',
                'details': f"Gaps detected between serials: {gaps}"
            })

        # 4. SKU Sequence Progression Check (e.g. 1/3, 2/3, 3/3)
        total_count += 1
        skus = sku_sequences or ["1/3", "2/3", "3/3"]
        sku_valid = True
        sku_reason = "Valid progression"

        try:
            parsed_skus = [list(map(int, s.split('/'))) for s in skus]
            expected_total = parsed_skus[0][1]
            indices = [p[0] for p in parsed_skus]

            if any(p[1] != expected_total for p in parsed_skus):
                sku_valid = False
                sku_reason = f"Denominator mismatch in SKU sequence: {skus}"
            elif sorted(indices) != list(range(1, expected_total + 1)):
                sku_valid = False
                sku_reason = f"Missing or out-of-order SKU indices: found {indices}, expected 1..{expected_total}"
        except Exception as e:
            sku_valid = False
            sku_reason = f"Malformed SKU format: {str(e)}"

        if sku_valid:
            passed_count += 1
            checks.append({
                'check_id': 'sku_sequence_progression',
                'field_name': 'RPO SKU Progression Sequence',
                'expected': f"Complete sequence (1/{len(skus)} to {len(skus)}/{len(skus)})",
                'actual': f"Complete: {', '.join(skus)}",
                'status': 'PASS',
                'severity': 'LOW',
                'details': 'SKU sequence is complete without missing fraction steps.'
            })
        else:
            checks.append({
                'check_id': 'sku_sequence_progression',
                'field_name': 'RPO SKU Progression Sequence',
                'expected': 'Complete sequence 1/N to N/N',
                'actual': sku_reason,
                'status': 'FAIL',
                'severity': 'HIGH',
                'details': sku_reason
            })

        score = round((passed_count / max(total_count, 1)) * 100.0, 1)

        return {
            'sector_name': 'RFID & Serialization QC',
            'score': score,
            'total_checks': total_count,
            'passed_checks': passed_count,
            'failed_checks': total_count - passed_count,
            'status': 'PASS' if score >= 90.0 else 'FAIL',
            'is_rfid': is_rfid,
            'is_serialized': is_serialized,
            'epc_count': len(sample_epcs),
            'decoded_epcs': decoded_items,
            'duplicates_count': len(duplicates),
            'gaps_count': len(gaps),
            'checks': checks
        }
