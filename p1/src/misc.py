def print_chunks(chunks, show_text=True):
    chunks = sorted(chunks, key=lambda c: (c.path, c.start_line, c.end_line))
    prev_path, prev_end = None, 0
    for c in chunks:
        if c.path != prev_path:
            print(f"\n{'#' * 80}\n# {c.path}\n{'#' * 80}")
            prev_path, prev_end = c.path, 0
        if c.start_line <= prev_end:
            print(f"!! OVERLAP: starts at {c.start_line}, previous ended at {prev_end}")
        elif c.start_line > prev_end + 1:
            print(f"   (gap: lines {prev_end + 1}-{c.start_line - 1} not in any chunk)")
        prev_end = max(prev_end, c.end_line)
        print(f"\n=== {c.chunk_id}  [{c.kind}]  {c.hash_value[:8]} ===")
        if show_text:
            for i, line in enumerate(c.text.splitlines() or [""], start=c.start_line):
                print(f"{i:5} | {line}")
    print(f"\n{len(chunks)} chunks total")