#!/usr/bin/env python3
"""Write declarative metadata around handwritten cases; never execute JavaScript."""
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = 'celld-os-project/celld/crates/celld/'

DESIGNS = [
    {
        'id': 'U201', 'title': 'Resolve relative asset URLs without mutating the base',
        'mechanism': 'Constructor host-op base resolution and hierarchical path normalization',
        'hypothesis': 'The URL host seam may resolve a relative reference against the full base path or accidentally retain the old query and fragment.',
        'application_relevance': 'Workers commonly derive resource and redirect targets from a request or configured base URL.',
        'trace': ['Construct one URL base with nondefault port, path, query, and fragment.', 'Construct one child with parent-directory and current-directory segments plus its own query and fragment.', 'Assert the exact child href and components, then the unchanged base href.'],
        'desired_behavior': 'Child is https://route.example.test:8443/docs/assets/icon.svg?theme=dark#outline; base is unchanged.',
        'source': [('js/url.js', 77, 100), ('js.rs', 10594, 10665)],
        'source_observation': 'Constructor delegates to the Rust url crate with a parsed base. This is coverage of the host seam, not a predicted failure.',
        'distinctness': 'Base-relative constructor resolution; no setter, query-list mutation, or URLPattern operation is the mechanism under test.',
    },
    {
        'id': 'U202', 'title': 'Encode pathname setter data without changing query or fragment',
        'mechanism': 'Path setter percent-encoding and component separation',
        'hypothesis': 'The pathname setter may copy Unicode and reserved path data directly into href, changing the meaning after reparsing.',
        'application_relevance': 'Workers compose file paths while preserving independent download-query and fragment state.',
        'trace': ['Construct one HTTPS URL with an existing query and fragment.', 'Assign /café/report?draft#notes as pathname data.', 'Assert encoded pathname, unchanged query and fragment, exact href, and fixed pathname after reparse.'],
        'desired_behavior': 'Path becomes /caf%C3%A9/report%3Fdraft%23notes, with ?download=yes#keep remaining independent.',
        'source': [('js/url.js', 166, 185), ('js/url.js', 235, 248)],
        'source_observation': 'Pinned pathname setter only removes ASCII line separators, optionally prepends slash, and copies the value. No percent-encoding step is visible. Source discrepancy hypothesis only.',
        'distinctness': 'Path-data encoding is independent of host canonicalization, numeric port conversion, and empty-delimiter preservation.',
    },
    {
        'id': 'U203', 'title': 'Canonicalize internationalized hostname assignments',
        'mechanism': 'Hostname setter IDNA and ASCII case normalization',
        'hypothesis': 'Hostname assignment may bypass the native host parser and serialize the input spelling rather than an ASCII domain.',
        'application_relevance': 'A Worker changing a configured catalog hostname needs consistent host and origin values while keeping its explicit port.',
        'trace': ['Construct one HTTPS catalog URL with port 8443.', 'Assign the valid internationalized hostname BÜCHER.example.', 'Assert hostname, host, origin, and full href against fixed punycode literals.'],
        'desired_behavior': 'All authority views use xn--bcher-kva.example and retain port 8443; path, query, and fragment are unchanged.',
        'source': [('js/url.js', 147, 151), ('js/url.js', 197, 228), ('js/url.js', 235, 248)],
        'source_observation': 'Pinned setter stores String(v) without IDNA or lowercasing. Source discrepancy hypothesis only.',
        'distinctness': 'Domain canonicalization; it does not test the IPv6 authority split exercised by U204.',
    },
    {
        'id': 'U204', 'title': 'Parse bracketed IPv6 host replacements and their ports',
        'mechanism': 'Host setter IPv6 bracket awareness and scheme-default port handling',
        'hypothesis': 'Splitting host at the first colon may corrupt a valid IPv6 literal and its port.',
        'application_relevance': 'Ordinary Worker endpoint configuration may use documentation-range IPv6 literals without making a network request.',
        'trace': ['Construct an HTTPS URL with existing port, path, query, and fragment.', 'Replace host with [2001:db8::7]:8443 and assert hostname, port, host, and href.', 'Replace with [2001:db8::8]:443 and assert default-port elision and origin.'],
        'desired_behavior': 'IPv6 brackets are preserved as part of hostname; only the colon after the closing bracket separates port.',
        'source': [('js/url.js', 126, 145), ('js/url.js', 197, 228)],
        'source_observation': 'Pinned host setter uses indexOf(\':\'), without bracket handling. Source discrepancy hypothesis only.',
        'distinctness': 'Authority tokenization rather than domain IDNA or direct numeric port conversion.',
    },
    {
        'id': 'U205', 'title': 'Normalize numeric port strings before default-port comparison',
        'mechanism': 'Port setter numeric representation and default elision',
        'hypothesis': 'Comparing raw digit strings to scheme defaults may retain leading zeroes and miss numeric default ports.',
        'application_relevance': 'Workers ingest ordinary padded port configuration and use origin or host as stable cache and routing keys.',
        'trace': ['Construct an HTTPS URL with an explicit nondefault port.', 'Set port to 00443 and assert empty port and no port in href.', 'Set port to 008443 and assert canonical 8443 plus origin.', 'Clear port and assert host without a port.'],
        'desired_behavior': '00443 is the default 443 and disappears; 008443 serializes as 8443; empty assignment clears the port.',
        'source': [('js/url.js', 34, 43), ('js/url.js', 153, 164)],
        'source_observation': 'Pinned setter accepts digit-only input but compares and stores the original string. Source discrepancy hypothesis only.',
        'distinctness': 'Numeric conversion happens in the direct port setter, not the IPv6 host grammar in U204.',
    },
    {
        'id': 'U206', 'title': 'Keep a live query view across href replacement',
        'mechanism': 'URL href replacement and same-object query-list rebinding',
        'hypothesis': 'Replacing href may detach a previously obtained searchParams object or leave an existing iterator reading the old list.',
        'application_relevance': 'A Worker can retain a local query view while replacing a redirect URL within one synchronous request.',
        'trace': ['Construct URL and save its query view and entries iterator.', 'Consume exactly one old tuple.', 'Replace href with a different authority and two-entry query.', 'Assert query object identity, replacement tuples, and the next existing-iterator tuple.', 'Append through the old view, assert new href and iterator tail, then exhaustion.'],
        'desired_behavior': 'The original view remains the same object bound to the new URL, and the iterator retains its index over the updated list.',
        'source': [('js/url.js', 86, 100), ('js/url.js', 230, 263), ('js/url_search_params.js', 146, 150), ('js/url_search_params.js', 227, 239)],
        'source_observation': 'Pinned _apply refreshes the existing query list. This case checks cross-object identity and iterator wiring; no observed runtime verdict.',
        'distinctness': 'Whole-URL replacement rebinding; U214 instead mutates an independent params list through its own API.',
    },
    {
        'id': 'U207', 'title': 'Preserve empty-present query and fragment delimiters',
        'mechanism': 'URL serialization distinction between absent and empty query/fragment',
        'hypothesis': 'Collapsing empty and absent fields into the same stored string may lose delimiters on an unrelated setter.',
        'application_relevance': 'Workers that rewrite a path must not silently change a URL serialized with explicit empty query or fragment markers.',
        'trace': ['Construct a URL ending in ?# and assert empty getters but exact serialized delimiters.', 'Set only pathname and assert both delimiters remain.', 'Clear query, then fragment, and assert each serialized state.', 'Assign search = ? and assert empty-present query serialization.'],
        'desired_behavior': 'The href sequence is /path?#, /next?#, /next#, /next, /next? while empty query and fragment getters remain empty strings.',
        'source': [('js/url.js', 86, 100), ('js/url.js', 166, 195), ('js/url.js', 235, 248), ('js.rs', 10631, 10643)],
        'source_observation': 'Host seam unwrap_or and JS truthiness flatten absent/empty fields, while initial href is retained separately. Source discrepancy hypothesis only.',
        'distinctness': 'Presence-state representation is independent of percent-encoding and live query object identity.',
    },
    {
        'id': 'U208', 'title': 'Mutate blob URL query and fragment without adding authority slashes',
        'mechanism': 'Opaque-path URL serialization with inherited blob origin',
        'hypothesis': 'The common href rebuild path may insert // after every scheme, corrupting an ordinary blob URL string.',
        'application_relevance': 'Worker code can inspect and decorate blob URL strings; this case neither creates nor dereferences a Blob object URL.',
        'trace': ['Construct one ordinary blob URL string with an embedded HTTPS origin and fixed UUID.', 'Assert inherited origin.', 'Set hash and assert exact opaque-path href.', 'Append a bound query pair and assert href, original pathname, and unchanged origin.'],
        'desired_behavior': 'The href continues to begin blob:https://, with ?mode=small#preview appended outside the embedded path.',
        'source': [('js/url.js', 188, 228), ('js/url.js', 235, 263)],
        'source_observation': 'Pinned origin code handles blob specially, but href reconstruction starts protocol + // for all schemes. Source discrepancy hypothesis only.',
        'distinctness': 'Opaque serialization versus the hierarchical HTTPS paths in U201-U207; no object URL lifecycle or retained capability.',
    },
    {
        'id': 'U209', 'title': 'Decode form queries with plus, duplicate keys, and first-equals splitting',
        'mechanism': 'application/x-www-form-urlencoded parsing into ordered tuples',
        'hypothesis': 'The form decoder may confuse plus with encoded plus, split a value at every equals, or manufacture tuples for empty separators.',
        'application_relevance': 'Workers read ordinary filter queries with repeated values, flags, and internationalized text.',
        'trace': ['Construct params from one fixed query string containing six meaningful tuples.', 'Assert the entire ordered tuple list.', 'Assert duplicate q values, bare flag value, absent-name null, and exact size.'],
        'desired_behavior': 'q values are blue sky and blue+sky; eq is a=b; flag is empty; snow is 雪; size is six.',
        'source': [('js/url_search_params.js', 3, 36), ('js/url_search_params.js', 75, 103), ('js/url_search_params.js', 152, 163)],
        'source_observation': 'Pinned parser has explicit plus conversion and first-equals split. Coverage of valid parsing only; no malformed encoding probes.',
        'distinctness': 'String decoding, not the opposite serialization path tested by U210.',
    },
    {
        'id': 'U210', 'title': 'Serialize form punctuation and Unicode with the form encode set',
        'mechanism': 'application/x-www-form-urlencoded tuple serialization',
        'hypothesis': 'A generic URI encoder may leave form-reserved punctuation unescaped or confuse literal plus with space.',
        'application_relevance': 'Workers construct ordinary query strings and URL-encoded form values from tuples.',
        'trace': ['Construct params from three fixed key/value pairs.', 'Assert the complete serialized form string.', 'Parse that string and assert the original tuples, then assert stored word was not mutated.'],
        'desired_behavior': 'Punctuation !\'()~ is escaped, *-._ remains, spaces become +, literal + becomes %2B, and Unicode uses fixed UTF-8 percent bytes.',
        'source': [('js/url_search_params.js', 66, 73), ('js/url_search_params.js', 111, 124), ('js/url_search_params.js', 220, 225)],
        'source_observation': 'Pinned serializer supplements encodeURIComponent for form-only punctuation. No observed runtime verdict.',
        'distinctness': 'Independent exact serialization oracle; round trip is secondary and cannot mask a mutually wrong encoder/decoder.',
    },
    {
        'id': 'U211', 'title': 'Coalesce duplicate params in place when setting a value',
        'mechanism': 'Ordered-multimap set replacement and live URL synchronization',
        'hypothesis': 'Set may keep later duplicates, move the first key to the end, or fail to synchronize the bound URL.',
        'application_relevance': 'Workers rewrite one filter while preserving other query ordering and a fragment.',
        'trace': ['Construct bound params with three a entries interleaved with b and c.', 'Set a once and assert exact tuples, size, and href.', 'Set previously absent d and assert it is appended after existing entries.'],
        'desired_behavior': 'The first a position becomes new value, later a entries vanish, b/c order stays, and absent d appends.',
        'source': [('js/url_search_params.js', 142, 144), ('js/url_search_params.js', 175, 193), ('js/url.js', 250, 263)],
        'source_observation': 'Pinned set filters duplicates and synchronizes once. This exercises its order-sensitive public effect.',
        'distinctness': 'Set replacement contract rather than selective removal or sort ordering.',
    },
    {
        'id': 'U212', 'title': 'Apply value-selective has and delete across repeated tuples',
        'mechanism': 'Optional value overloads for multimap membership and removal',
        'hypothesis': 'The optional value argument may be ignored or empty-string filtering may accidentally act as name-only deletion.',
        'application_relevance': 'Workers remove selected tags while preserving other values and unrelated query fields.',
        'trace': ['Construct repeated red, blue, and empty tag values with unrelated x.', 'Assert empty-value membership, delete red, then assert exact survivors and membership.', 'Delete only empty tag values and verify.', 'Delete remaining tag values by name and assert only x remains.'],
        'desired_behavior': 'Value filtering removes all matching tuples and leaves other values; omitted value removes all tuples for the name.',
        'source': [('js/url_search_params.js', 165, 173), ('js/url_search_params.js', 201, 212), ('js/url_search_params.js', 249, 250)],
        'source_observation': 'Pinned has/delete distinguish undefined from an empty value. Test inputs use only provided strings or omission.',
        'distinctness': 'Overload selection and selective removal, not U211 duplicate coalescing.',
    },
    {
        'id': 'U213', 'title': 'Sort query keys stably by UTF-16 and synchronize canonical form encoding',
        'mechanism': 'Stable code-unit sort plus bound URL query reserialization',
        'hypothesis': 'Sorting may use Unicode code-point order, reorder equal keys, or omit the bound URL update.',
        'application_relevance': 'Workers sort cache-key queries containing repeated values and Unicode keys.',
        'trace': ['Construct a bound URL query with duplicate a, astral and BMP keys, encoded spaces, and a tilde.', 'Sort once and assert full key order, duplicate order, exact search, and retained fragment.', 'Sort again and assert the same fixed search string.'],
        'desired_behavior': 'Keys sort a,a,space,tilde,z,😀,U+E000; duplicates remain first/second; bound query uses + and %7E.',
        'source': [('js/url_search_params.js', 214, 225), ('js/url.js', 250, 263)],
        'source_observation': 'Pinned comparator uses JS string ordering and stable Array.sort. This checks the complete observable result with fixed literals.',
        'distinctness': 'Ordering algorithm and reserialization side effect rather than scalar insertion/removal.',
    },
    {
        'id': 'U214', 'title': 'Keep a live params iterator current across a temporary list end',
        'mechanism': 'Web IDL pair-iterator liveness and list-length rechecking',
        'hypothesis': 'An iterator may snapshot the initial list, retain a deleted tuple, miss an updated value, or latch completion instead of rechecking the list.',
        'application_relevance': 'Workers may adjust query fields while performing one bounded traversal.',
        'trace': ['Create params a,b,c and consume one tuple.', 'Delete unseen b and append d; assert next tuple c.', 'Update unseen d and assert updated tuple.', 'Observe done, append e, assert the same iterator yields e and then reports done again; verify fresh iterator final keys.'],
        'desired_behavior': 'Existing iterator yields a,c,updated d, reports done, then yields e after append and reports done again. Web IDL pair iterators do not latch a completed state.',
        'source': [('js/url_search_params.js', 175, 212), ('js/url_search_params.js', 227, 239)],
        'source_observation': 'Pinned generator uses dynamic length during traversal but latches completion when its body ends; Web IDL pair next instead rechecks the target list on every call. Source discrepancy hypothesis only.',
        'distinctness': 'Iterator state across direct list mutation; U206 instead replaces an owning URL record.',
    },
    {
        'id': 'U215', 'title': 'Return detached arrays from params entries',
        'mechanism': 'Web IDL pair-iterator result ownership',
        'hypothesis': 'Yielding the internal tuple array may let an ordinary consumer edit bypass params methods and later leak into URL serialization.',
        'application_relevance': 'Workers commonly edit a destructured or collected entries array before constructing a different query.',
        'trace': ['Construct a bound query and read one entries tuple.', 'Edit the returned array locally.', 'Assert original params name/value and a fresh full iteration are unchanged.', 'Append through the public API and assert href contains no consumer edits; assert the local array kept those edits.'],
        'desired_behavior': 'The returned pair is a new array; editing it has no effect on params or its owning URL.',
        'source': [('js/url_search_params.js', 227, 239), ('js/url_search_params.js', 195, 199), ('js/url.js', 250, 254)],
        'source_observation': 'Pinned entries yields this.#params[i] directly. Source discrepancy hypothesis only.',
        'distinctness': 'Result aliasing and ownership, not iterator traversal liveness. No prototype mutation or invalid pair input.',
    },
    {
        'id': 'U216', 'title': 'Prefer iterable constructor input and copy its values eagerly',
        'mechanism': 'Constructor iterable-versus-record selection and detached snapshots',
        'hypothesis': 'Construction may enumerate record keys despite an iterator or retain the input pair arrays and source params by reference.',
        'application_relevance': 'Workers adapt iterable key/value sources and clone a query before changing it.',
        'trace': ['Construct params from a two-pair custom iterable that also has an enumerable record key.', 'Edit and extend the source arrays after construction.', 'Assert one iterator visit, exact copied pairs, and no record-key entry.', 'Copy the params, then mutate the original and assert the copy is unchanged.'],
        'desired_behavior': 'Iterable input wins, is consumed once, and both array-pair and params-copy construction take detached snapshots.',
        'source': [('js/url_search_params.js', 97, 140)],
        'source_observation': 'Pinned constructor checks iterator before record conversion and creates new pairs. Valid two-element iterables only.',
        'distinctness': 'Constructor overload and input lifetime versus the output-pair lifetime in U215.',
    },
    {
        'id': 'U217', 'title': 'Resolve URLPattern base inputs and preserve result input arguments',
        'mechanism': 'URLPattern string/base overload and canonicalized match-input host seam',
        'hypothesis': 'Pattern or input base resolution may disagree, or the result may confuse raw input arguments with canonicalized component inputs.',
        'application_relevance': 'Workers build routers relative to a service base and need both captured route values and traceable original inputs.',
        'trace': ['Construct a relative items/:id pattern against one base.', 'Match one relative input with an uppercase-host, explicit-default-port base.', 'Assert pattern path, nonnull result, raw inputs array, canonical host/port/path, and id capture.', 'Assert a valid URL under another path is a nonmatch.'],
        'desired_behavior': 'Relative route is /catalog/items/:id; input canonicalizes to shop.example.test and empty port, captures 42, and retains both raw arguments.',
        'source': [('js/url_pattern.js', 19, 33), ('js/url_pattern.js', 37, 59), ('js/url_pattern.js', 79, 97), ('js.rs', 10675, 10765)],
        'source_observation': 'Native ops canonicalize while JS constructs inputs separately. This verifies the seam rather than duplicating plain URL constructor behavior.',
        'distinctness': 'Pattern constructor and exec base overload, input provenance, and canonical component mapping.',
    },
    {
        'id': 'U218', 'title': 'Represent optional URLPattern captures and isolate exec result objects',
        'mechanism': 'Optional pathname group materialization and result freshness',
        'hypothesis': 'An unmatched group may be omitted or represented as empty string, or mutation of one result may affect later matches.',
        'application_relevance': 'Workers route collection and item URLs through one pattern and inspect optional named fields.',
        'trace': ['Construct /books/:id? and exec both collection and item URLs.', 'Assert both match; optional group exists with undefined value when absent and 42 when present.', 'Edit the present result and exec again to assert fresh groups.', 'Reject a valid URL with an extra segment and assert no custom regexp groups.'],
        'desired_behavior': 'Absent optional id is an own property with undefined value; result edits do not affect a later exec.',
        'source': [('js/url_pattern.js', 69, 97), ('js.rs', 10703, 10719)],
        'source_observation': 'JS maps regex captures into a freshly allocated groups object. Optional-group undefined is explicitly asserted before JSON serialization.',
        'distinctness': 'Optional capture shape and per-call result ownership, rather than base resolution or regexp restriction.',
    },
    {
        'id': 'U219', 'title': 'Apply URLPattern ignoreCase across components without changing captures',
        'mechanism': 'URLPattern option propagation to compiled component regex flags',
        'hypothesis': 'ignoreCase may apply only to a subset of components or normalize the text returned in captures.',
        'application_relevance': 'Workers build case-insensitive document routes while retaining user-supplied capture spelling.',
        'trace': ['Construct the same multi-component pattern once with ignoreCase and once with the default option.', 'Match a single differently cased path/query/fragment input and assert opposite verdicts.', 'Assert original capture spelling and hash input.', 'Assert an unrelated fragment still does not match.'],
        'desired_behavior': 'Case-insensitive pattern matches, default does not; captures remain Guide and Read and unrelated fragment remains excluded.',
        'source': [('js/url_pattern.js', 37, 59), ('js/url_pattern.js', 71, 97), ('js.rs', 10679, 10701)],
        'source_observation': 'Pinned code passes ignoreCase to Rust compilation and chooses ui flags in JS. Both paths must agree.',
        'distinctness': 'One option-propagation mechanism with a within-case control; the two options do not count as two designs.',
    },
    {
        'id': 'U220', 'title': 'Enforce custom regexp and all URLPattern component constraints',
        'mechanism': 'Custom regexp-group metadata and eight-component conjunction',
        'hypothesis': 'Custom group metadata or group-name mapping may be lost at the host seam, or one successful component may mask another component nonmatch.',
        'application_relevance': 'Workers route numeric order IDs only for one hostname and a required query shape.',
        'trace': ['Construct fixed numeric-id pathname and named search capture patterns for api.example.test.', 'Assert custom-regexp flag and exact captures on one matching URL.', 'Exec a valid draft-string ID URL and require null.', 'Require false for valid URLs with the wrong query shape or hostname.'],
        'desired_behavior': '2048 and full are separate named captures; nonnumeric id, wrong search key, and wrong hostname each prevent a match.',
        'source': [('js/url_pattern.js', 69, 97), ('js.rs', 10703, 10719), ('js.rs', 10724, 10765)],
        'source_observation': 'Rust returns regex and group-name metadata; JS uses every component for test and stops exec on the first nonmatch.',
        'distinctness': 'Custom regexp restriction and conjunction across components, not optional capture shape or ignoreCase.',
    },
]

text = (HERE / 'cases.js').read_text()
limits = {
    'requests_per_case': 1,
    'repetitions': 1,
    'request_body_bytes': 0,
    'concurrent_requests': 1,
    'request_outer_deadline_seconds': 5,
    'response_max_bytes': 65536,
    'case_input_max_code_units': 1024,
    'case_tuple_max_count': 16,
    'case_assertion_max_count': 16,
    'network_calls_from_fixture': 0,
    'storage_writes_from_fixture': 0,
    'timers_from_fixture': 0,
}
for design in DESIGNS:
    case_id = design['id']
    match = re.search(r'^  ' + case_id + r'\(t\) \{\n(.*?)^  \},', text, re.M | re.S)
    assert match, case_id
    body = match.group(1)
    line = text[:match.start()].count('\n') + 1
    refs = design.pop('source')
    design.update({
        'layer': 'direct-celld-worker-fetch-global-web-api',
        'entrypoint': {'method': 'GET', 'path': '/case/' + case_id, 'request_body': None},
        'implementation': {'file': 'cases.js', 'symbol': case_id, 'start_line': line, 'end_line': line + match.group(0).count('\n')},
        'fixed_runtime_assertions': [line.strip() for line in body.splitlines() if re.search(r't\.(equal|deep)\(', line)],
        'assertion_count': len(re.findall(r't\.(?:equal|deep)\(', body)),
        'runtime_source_refs': [{'path': SOURCE + path, 'line_start': start, 'line_end': end} for path, start, end in refs],
        'preconditions': ['Fresh isolated fixture deployment on the exact reviewed direct-celld build; external source/build/process witness required.', 'Global URL, URLSearchParams, and for U217-U220 URLPattern are supplied by celld, not by Node, a shim, or a mock.', 'External finite-deadline supervisor and owned-process cleanup are available; missing runtime prerequisites are BLOCKED.'],
        'schedule': {'kind': 'one synchronous finite trace', 'request_ordinal': int(case_id[1:]) - 200, 'path': '/case/' + case_id, 'depends_on': [], 'overlap': 'none', 'runtime_operations': design['trace']},
        'limits': limits,
        'cleanup': 'All URL, params, iterator, pattern, array, and result values are request-local. Return from synchronous fetch releases references. No timer, outgoing fetch, binding, durable write, object URL allocation, or retained cross-request capability. External supervisor stops only owned processes and deletes only its fresh deployment/store directory after receipt capture.',
        'ordinary_input_scope': 'Successful public API calls on complete ordinary URL strings or valid property, pair, and pattern inputs. Valid URL nonmatches are intentional boolean/null outcomes, never malformed-input probes. Example domains and documentation IPv6 addresses are data only.',
        'authored': True,
        'independently_reviewed': False,
        'review_status': 'UNREVIEWED',
        'status': 'NOT_RUN',
        'runtime_status': 'UNRUN',
        'actual_runtime_executions': 0,
        'runtime_pass_claimed': False,
        'candidate_classification': 'assertion-bearing ordinary API correctness candidate; no reviewed census credit yet',
    })
    predicted_gaps = {'U202', 'U203', 'U204', 'U205', 'U207', 'U208', 'U214', 'U215'}
    design['static_prediction'] = 'EXPECTED_FAILURE_CANDIDATE' if case_id in predicted_gaps else 'NO_FAILURE_PREDICTION'
    design['prediction_is_runtime_evidence'] = False
    if case_id in {'U214', 'U215'}:
        design['primary_contract_refs'] = ['https://url.spec.whatwg.org/#urlsearchparams', 'https://webidl.spec.whatwg.org/#es-iterable-iterator-prototype-object']
    elif int(case_id[1:]) <= 208:
        anchor = {'U202': 'dom-url-pathname', 'U203': 'dom-url-hostname', 'U204': 'dom-url-host', 'U205': 'dom-url-port', 'U207': 'dom-url-search', 'U208': 'concept-url-serializer'}.get(case_id, 'url-class')
        design['primary_contract_refs'] = ['https://url.spec.whatwg.org/#' + anchor]
    elif int(case_id[1:]) <= 216:
        design['primary_contract_refs'] = ['https://url.spec.whatwg.org/#urlsearchparams']
    else:
        design['primary_contract_refs'] = ['https://urlpattern.spec.whatwg.org/']

manifest = {
    'schema_version': 1,
    'profile': 'direct-celld-url-semantics-v1',
    'source_snapshot': 'celld-direct-source-v0.6.2-8d27-guard-20261009',
    'authored_case_count': len(DESIGNS),
    'reviewed_case_count': 0,
    'runtime_executions': 0,
    'runtime_status': 'UNRUN',
    'qualification': 'Handwritten executable source and declarative fixed oracles only. Syntax validation is not execution, external review, or SUT evidence.',
    'oracle_policy': 'Literal expected values are authored from ordinary API contracts and independent of pinned implementation output. Fixed runtime assertions below are copied verbatim from handwritten source, not derived by running any URL implementation. Source-discrepancy observations describe the implementation separately from desired behavior.',
    'contract_references': [
        {'url': 'https://url.spec.whatwg.org/#url-class', 'purpose': 'URL setters, parsing, serialization, and query object identity; consulted 2026-10-09'},
        {'url': 'https://url.spec.whatwg.org/#urlsearchparams', 'purpose': 'Ordered parameter methods and form encoding; consulted 2026-10-09'},
        {'url': 'https://webidl.spec.whatwg.org/#es-iterator-next', 'purpose': 'Pair iterator creates a new array for the returned pair; consulted 2026-10-09'},
        {'url': 'https://urlpattern.spec.whatwg.org/', 'purpose': 'URLPattern overloads, matching, captures and options; consulted 2026-10-09'},
    ],
    'exclusions': ['No malformed-input or authentication probes', 'No forged routes, replay, fault injection, or retained stateless capabilities', 'No G/N/P/J122 guarded paths or native coordination tests', 'No hidden runtime implementation imports or source changes', 'No Node or reference-runtime execution is counted as SUT evidence'],
    'cases': DESIGNS,
}
(HERE / 'manifest.json').write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + '\n')
