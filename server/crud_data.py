from datetime import datetime
from typing import Union, Optional
from sqlalchemy.orm import Session
from sqlalchemy.engine import Engine
from sqlalchemy import func
from sql_data import TextEntry, User, TTSRequest, UsageStatistic


def engine_to_session(func):
    def wrapper(*args, **kwargs):
        args = list(args)
        engine = args[0]

        if isinstance(engine, Engine):
            with Session(engine) as db:
                return func(db, *args[1:], **kwargs)
        elif isinstance(engine, Session):
            return func(engine, *args[1:], **kwargs)
        else:
            raise ValueError("Invalid engine type")

    return wrapper


def object_to_dict(obj):
    """
    Convert SQLAlchemy model object to dictionary, handling datetime serialization
    """
    if obj is None:
        return None

    data = {}
    for key, value in obj.__dict__.items():
        if key.startswith("_"):
            continue
        if isinstance(value, datetime):
            data[key] = value.isoformat()
        else:
            data[key] = value
    return data


@engine_to_session
def create_text_entry(
    db: Union[Session, Engine],
    text_id: str,
    user_sub: str,
    full_text: str,
    url: str,
) -> TextEntry:
    """
    Create a new text entry in the database
    """
    text_entry = TextEntry(
        text_id=text_id,
        user_sub=user_sub,
        full_text=full_text,
        url=url,
    )
    db.add(text_entry)
    db.commit()
    db.refresh(text_entry)
    return text_entry


@engine_to_session
def get_text_entry(db: Union[Session, Engine], text_id: str) -> TextEntry:
    """
    Get a text entry by its ID
    """
    return db.query(TextEntry).filter(TextEntry.text_id == text_id).first()


@engine_to_session
def get_user_text_entries(db: Union[Session, Engine], sub: str, skip: int = 0, limit: int = 100):
    """
    Get all text entries for a user with pagination
    """
    text_entry_list = (
        db.query(TextEntry)
        .filter(TextEntry.user_sub == sub)
        .order_by(TextEntry.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    result = []
    for entry in text_entry_list:
        row = object_to_dict(entry)
        result.append(row)
    return result


@engine_to_session
def create_user(db: Union[Session, Engine], sub: str, email: str, name: str) -> User:
    """
    Create a new user in the database
    """
    user = User(sub=sub, email=email, name=name, last_login_at=datetime.now())
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@engine_to_session
def get_user(db: Union[Session, Engine], sub: str) -> User:
    """
    Get a user by their ID
    """
    return db.query(User).filter(User.sub == sub).first()


@engine_to_session
def get_user_by_email(db: Union[Session, Engine], email: str) -> User:
    """
    Get a user by their email address
    """
    return db.query(User).filter(User.email == email).first()


@engine_to_session
def make_sure_user_exists(db: Union[Session, Engine], sub: str, email: str, name: str) -> User:
    """
    Make sure a user exists in the database
    """
    user = get_user(db, sub)
    if not user:
        user = create_user(db, sub, email, name)
    return user


@engine_to_session
def user_login(db: Union[Session, Engine], sub: str, email: str, name: str) -> User:
    """
    Update user last login time
    """
    user = make_sure_user_exists(db, sub, email, name)
    user.last_login_at = datetime.now()
    db.commit()
    db.refresh(user)
    return user


@engine_to_session
def update_user(db: Union[Session, Engine], sub: str, **kwargs) -> User:
    """
    Update user fields
    """
    user = get_user(db, sub)
    if user:
        for key, value in kwargs.items():
            setattr(user, key, value)
        db.commit()
        db.refresh(user)
    return user


@engine_to_session
def create_tts_request(
    db: Union[Session, Engine],
    text_entry_id: str,
    user_sub: str,
    sentence_text: str,
    sentence_index: int,
    audio_id: str,
    character_count: int,
    processing_time_ms: Optional[int] = None,
    voice_model: str = "aura-asteria-en",
    status: str = "completed",
    error_message: Optional[str] = None,
) -> TTSRequest:
    """Create a new TTS request record"""
    tts_request = TTSRequest(
        text_entry_id=text_entry_id,
        user_sub=user_sub,
        sentence_text=sentence_text,
        sentence_index=sentence_index,
        audio_id=audio_id,
        character_count=character_count,
        processing_time_ms=processing_time_ms,
        voice_model=voice_model,
        status=status,
        error_message=error_message,
        created_by=user_sub,
        updated_by=user_sub,
    )
    db.add(tts_request)
    db.commit()
    db.refresh(tts_request)
    return tts_request


@engine_to_session
def get_tts_request(db: Union[Session, Engine], audio_id: str) -> Optional[TTSRequest]:
    """Get a TTS request by its audio ID"""
    return db.query(TTSRequest).filter(TTSRequest.audio_id == audio_id).first()


@engine_to_session
def get_tts_requests(
    db: Union[Session, Engine],
    user_sub: str,
    limit: int = 10,
):
    """Get recent TTS requests for a user"""
    tts_requests = (
        db.query(TTSRequest)
        .filter(TTSRequest.user_sub == user_sub)
        .order_by(TTSRequest.created_at.desc())
        .limit(limit)
        .all()
    )

    results = []
    for tts_request in tts_requests:
        results.append(object_to_dict(tts_request))
    return results
