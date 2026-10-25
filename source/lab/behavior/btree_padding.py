"""Unused native BTree header bytes must come from initialized fixture storage."""
# StarBTreeDatabase.hpp: selector32, two17-byte root slots at33; reserved
# header ends at512. These are on-disk offsets, not a C++ object layout.
PADDING_START = 33 + 2 * 17
HEADER_SIZE = 512


def validate_pages(pages):
    if type(pages) is not bytes or len(pages) < HEADER_SIZE:
        raise ValueError('BTree header padding: short/non-byte device image')
    if pages[PADDING_START:HEADER_SIZE] != bytes(HEADER_SIZE - PADDING_START):
        raise ValueError('BTree header padding: initialized zero backing required')
