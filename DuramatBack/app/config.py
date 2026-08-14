from dataclasses import dataclass


@dataclass(frozen=True)
class AppSettings:
    app_name: str = "Duramat Decision Engine"
    app_version: str = "1.0.0"
    debug: bool = False
    allowed_origins: list[str] | None = None

    def __post_init__(self):
        if self.allowed_origins is None:
            object.__setattr__(
                self,
                "allowed_origins",
                [
                    "http://localhost:8080",
                    "http://127.0.0.1:8080",
                    "http://localhost",
                    "http://127.0.0.1",
                        "https://duramat.vercel.app",
                ],
            )


settings = AppSettings()
