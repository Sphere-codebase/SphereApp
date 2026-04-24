import threading
import time

from sqlalchemy.orm import Session, sessionmaker

from app.core.tenancy import reset_current_is_platform_admin, set_current_is_platform_admin
from app.db.id_utils import next_id
from app.db.models import Role


def test_next_id_serializes_concurrent_writers(db_session: Session) -> None:
    engine = db_session.get_bind()
    assert engine is not None
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, class_=Session)
    barrier = threading.Barrier(2)
    results: list[int] = []
    errors: list[Exception] = []
    result_lock = threading.Lock()

    def worker(index: int) -> None:
        token = set_current_is_platform_admin(True)
        session = SessionLocal()
        try:
            barrier.wait(timeout=5)
            role_id = next_id(session, Role)
            session.add(
                Role(
                    id=role_id,
                    code=f"concurrent_role_{index}",
                    description="Concurrent role",
                )
            )
            time.sleep(0.2)
            session.commit()
            with result_lock:
                results.append(role_id)
        except Exception as exc:  # pragma: no cover - assertion covers unexpected failures
            session.rollback()
            with result_lock:
                errors.append(exc)
        finally:
            session.close()
            reset_current_is_platform_admin(token)

    threads = [threading.Thread(target=worker, args=(index,)) for index in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)

    assert not errors

    inserted = (
        db_session.query(Role)
        .filter(Role.code.in_(["concurrent_role_0", "concurrent_role_1"]))
        .order_by(Role.id.asc())
        .all()
    )
    assert len(inserted) == 2
    assert len({role.id for role in inserted}) == 2
