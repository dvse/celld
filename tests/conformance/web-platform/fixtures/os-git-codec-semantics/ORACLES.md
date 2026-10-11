# Independent format oracles

No expected value was learned by running git-codec.ts, Git, Node, pako, workerd or celld. The authoring helper uses Python standard-library byte construction and hashes. Its stored-block zlib inputs are hand-format fixtures, not a reference codec invoked by the runtime tests. Runtime assertions import the unmodified production module.

## X201: loose object

[Git's object-format walkthrough](https://git-scm.com/book/en/v2/Git-Internals-Git-Objects#_object_storage) supplies the independently published blob content `what is up, doc?` and OID `bd9dbf5aae1a3862dd1526723246b20206e5fc37`. The 16-byte payload is preceded by `blob 16` and a NUL. The fixed decoder input uses a single stored DEFLATE block. The encoder's output is independently inflated and compared with this literal whole; compressed bytes are intentionally unrestricted.

## X202: tree

[Git v2.50.0 tree.c, base_name_compare, lines 95–110](https://github.com/git/git/blob/v2.50.0/tree.c#L95-L110) compares unsigned bytes and substitutes slash at a directory's end. Therefore `a.b`, directory `a`, and `a0` have this exact order, followed by `link` and `sub`. [Git fast-import's mode descriptions](https://git-scm.com/docs/git-fast-import#_filemodify) identify regular/executable files, symlinks, subdirectories and gitlinks. The literal tree contains all five, their raw 20-byte OIDs, and exact NUL separators. Separate golden referent objects provide a real empty tree, link target and root commits; no invalid OID or missing-structure test is involved.

## X203: commit

The Git object walkthrough describes commit tree/parent/identity/message structure. The production public encoder contract at lines 345–394 further specifies parent/header order and message normalization. The expected text is authored directly, without calling an encoder. Millisecond timestamps 1700000000999 and 1700000001999 represent whole seconds 1700000000 and 1700000001; offsets 330 and -210 minutes produce +0530 and -0330. Ordered parent IDs refer to separately authored valid root commits. A separate ordinary custom `x-note` header has continued values, including an empty continued line and a line with two leading spaces whose value retains one. [Git's multiline-header rule](https://git-scm.com/docs/gitformat-signature#_description) supports removing one leading space per continuation. No cryptographic signature bytes, validation, identity claim or authorization mechanism is exercised.

## X204: delta

[Git pack delta instruction specification](https://git-scm.com/docs/gitformat-pack#_deltified_representation) defines source/result size varints, literal inserts, optional little-endian copy fields, and the omitted-size 65536-byte copy. Our single valid instruction sequence is:

- `80 80 04`: source size 65536
- `99 80 04`: target size 65561
- `05` and `HEAD|`: insert five bytes
- `80`: copy 65536 bytes from source offset zero
- `93 01 01 10`: copy sixteen bytes from source offset 257
- `04` and `|END`: insert four bytes

The base is byte values 0 through 255 repeated 256 times. The literal target is `HEAD|`, the whole base, byte values 1 through 16, then `|END`. A full literal SHA-256 supplements exact byte comparison. This is one compound mechanism, not separate boundary values counted as cases.

## X205 and X206: complete packs

[Git pack format](https://git-scm.com/docs/gitformat-pack#_pack_pack_files_have_the_following_format) supplies PACK/version/count, type/size fields and a body-only SHA-1 trailer. The four-object pack contains a blob, its tree, a parentless commit and an unsigned annotated tag referring to that commit. Header sizes are explicit low-four/high-seven-bit fields. The encoder is checked through its joined header, actual-body digest and complete decoding against fixed object expectations. Its compressed bytes and chunk partition need not match the fixed pack. A separate decoder pass uses the independently assembled golden. Both passes require literal object bytes/OIDs, exact object count and completed generators.

The distinct chain pack has entry starts 12, 281 and 309. Its first entry spans 269 bytes. OFS bytes `81 0d` therefore encode `(1 + 1) × 128 + 13 = 269`, pointing from 281 back to 12. The middle payload is source bytes 17–24 plus `-middle`. REF bytes identify that middle object's independently computed OID, and its delta appends `!`. The retained-object map is populated immediately after each yield, before requesting the next object. The resolver contract at production lines 498–517 and the format's base-reference definition justify both lookups. The entire generator must complete before any trailer assertion is accepted as successful decoding.

## Stored-block construction and verification

[RFC 1950 §2.2](https://www.rfc-editor.org/rfc/rfc1950#section-2.2) and [RFC 1951 §3.2.4](https://www.rfc-editor.org/rfc/rfc1951#section-3.2.4) define the wrappers used only for fixed input construction: zlib header 78 01; final uncompressed DEFLATE block byte 01; 16-bit little-endian LEN and its one's complement; payload; big-endian Adler-32. Python static validation checks these fixed structures, object SHA-1 values and pack trailers. It does not evaluate production code or produce runtime PASS evidence.
