"""Run directly in a local terminal; never pass a key as a command argument."""

import getpass
import os
import re
import sys
import warnings
from pathlib import Path

DESTINATION = Path(__file__).resolve().parents[1] / "apps/api/.env"


def main() -> int:
    if not sys.stdin.isatty():
        print(
            "직접 조작하는 터미널에서 실행해 주세요. 표준 입력/파이프는 받지 않습니다."
        )
        return 1
    if DESTINATION.exists() or DESTINATION.is_symlink():
        print("기존 설정 파일이 있어 중단했습니다. 기존 파일을 덮어쓰지 않습니다.")
        return 1
    print(f"저장 위치: {DESTINATION} (소유자만 읽기/쓰기)")
    print(
        "키 입력은 화면에 표시되지 않습니다. 저장만 하며 API 호출/클라우드 업로드는 없습니다."
    )
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", getpass.GetPassWarning)
            key = getpass.getpass("OpenAI API key: ")
        if not re.fullmatch(r"sk-[A-Za-z0-9_-]{20,512}", key):
            print("키 형식이 맞지 않아 저장하지 않았습니다.")
            return 1
        payload = f"JHWORKS_OPENAI_API_KEY={key}\nJHWORKS_AI_ENABLED=false\n"
        descriptor = os.open(DESTINATION, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w") as output:
            output.write(payload)
        print("키 저장 완료. 실제 AI 호출은 아직 비활성 상태입니다.")
        return 0
    except (EOFError, KeyboardInterrupt):
        print("\n취소했습니다.")
        return 1
    except (OSError, getpass.GetPassWarning):
        print("보안 입력/저장을 완료하지 못했습니다. 진단에 키를 출력하지 않습니다.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
