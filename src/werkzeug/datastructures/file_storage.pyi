from os import PathLike
from typing import Any
from typing import Dict
from typing import IO
from typing import Iterator
from typing import Optional
from typing import Tuple
from typing import Union

from .headers import Headers
from .structures import MultiDict

class FileStorage:
    name: Optional[str]
    stream: IO[bytes]
    filename: Optional[str]
    headers: Headers
    _parsed_content_type: Tuple[str, Dict[str, str]]
    def __init__(
        self,
        stream: Optional[IO[bytes]] = None,
        filename: Union[str, PathLike, None] = None,
        name: Optional[str] = None,
        content_type: Optional[str] = None,
        content_length: Optional[int] = None,
        headers: Optional[Headers] = None,
    ) -> None: ...
    def _parse_content_type(self) -> None: ...
    @property
    def content_type(self) -> str: ...
    @property
    def content_length(self) -> int: ...
    @property
    def mimetype(self) -> str: ...
    @property
    def mimetype_params(self) -> Dict[str, str]: ...
    def save(
        self, dst: Union[str, PathLike, IO[bytes]], buffer_size: int = ...
    ) -> None: ...
    def close(self) -> None: ...
    def __bool__(self) -> bool: ...
    def __getattr__(self, name: str) -> Any: ...
    def __iter__(self) -> Iterator[bytes]: ...
    def __repr__(self) -> str: ...

class FileMultiDict(MultiDict[str, FileStorage]):
    def add_file(
        self,
        name: str,
        file: Union[FileStorage, str, IO[bytes]],
        filename: Optional[str] = None,
        content_type: Optional[str] = None,
    ) -> None: ...
