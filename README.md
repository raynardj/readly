# Readly

> You can listen to information much faster than you can read it.

> This is Xiaochen(Ray) Zhang's Mastery Assignment @nau, CS560. Will make this repo private right after the scoring is over.

## Client Side
The front end is a Chrome extension.

Install the folder `readly-chrome` as an unpacked extension in Chrome.

## Server Side
Server side is using `FastAPI` (python) to run an HTTPS service

### Have the sentence splitter model
```
python -m spacy download en_core_web_sm
```

### Initialize the database
This is very temporary, just for testing. It should be migration code in the future.
```python
from sql_data import build_engine
engine, init_db, drop_db = build_engine()
init_db()
```

