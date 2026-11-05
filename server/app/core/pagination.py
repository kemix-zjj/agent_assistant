"""分页参数依赖。"""

from fastapi import Query


class PageParams:
    def __init__(
        self,
        page: int = Query(default=1, ge=1, description="页码，从 1 开始"),
        page_size: int = Query(
            default=12, ge=1, le=50, alias="pageSize", description="每页条数，最大 50"
        ),
    ) -> None:
        self.page = page
        self.page_size = page_size

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size
