import pymupdf 

doc = pymupdf.open("data/wholesale.pdf") # open a document
for page in doc: # iterate the document pages
  text = page.get_text() # get plain text encoded as UTF-8