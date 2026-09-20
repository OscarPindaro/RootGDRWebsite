from sqlalchemy import Enum as SAEnum, String
from sqlalchemy.orm import Mapped, mapped_column

from ..db.db import Base
from ..db.enums import SymbolStyle, UserRole
from ..db.mixins import TimestampMixin, UUIDv7PrimaryKeyMixin


class UserModel(Base, UUIDv7PrimaryKeyMixin, TimestampMixin):
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    avatar_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    symbol_style: Mapped[SymbolStyle] = mapped_column(
        SAEnum(SymbolStyle, name="symbol_style"),
        nullable=False,
        default=SymbolStyle.ICONS,
    )
    role: Mapped[UserRole] = mapped_column(
        SAEnum(UserRole, name="user_role"), nullable=False, default=UserRole.MEMBER
    )
    is_active: Mapped[bool] = mapped_column(default=True)
