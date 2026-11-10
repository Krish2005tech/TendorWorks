import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(prog="tender")
    commands = parser.add_subparsers(dest="command", required=True)
    serve = commands.add_parser("serve", help="Start the web application")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8000)
    commands.add_parser("ingest", help="Index new and changed source files in database/")
    drafts = commands.add_parser("draft-packs", help="Create review-only candidate packs from eligible PDF files")
    drafts.add_argument("--rebuild", type=Path, help="Rebuild a draft pack using approved rows from this review XLSX")
    drafts.add_argument("--pack", type=Path, help="Draft .pack.json used with --rebuild")
    commands.add_parser("schema", help="Print the domain package JSON schema")
    demo = commands.add_parser("demo-package", help="Write a synthetic example domain package")
    demo.add_argument("path", type=Path)
    evaluate = commands.add_parser(
        "evaluate", help="Run reference cases without modifying authoritative data"
    )
    evaluate.add_argument("cases", type=Path)
    args = parser.parse_args()
    if args.command == "serve":
        import uvicorn

        uvicorn.run("tender.app:create_app", factory=True, host=args.host, port=args.port)
    elif args.command == "schema":
        from tender.schemas import DomainPack

        print(json.dumps(DomainPack.model_json_schema(), indent=2))
    elif args.command == "demo-package":
        from tender.demo import demo_pack

        args.path.parent.mkdir(parents=True, exist_ok=True)
        args.path.write_text(demo_pack().model_dump_json(indent=2))
        print(f"Synthetic example written to {args.path}")
    else:
        from tender.config import Settings
        from tender.db import Repository
        from tender.ingestion import FolderIngestor
        from tender.knowledge import KnowledgeGateway
        from tender.storage import ObjectStore

        settings = Settings()
        repo = Repository(settings)
        gateway = KnowledgeGateway(repo, ObjectStore(settings), settings)
        ingestor = FolderIngestor(gateway)
        if args.command == "ingest":
            print(json.dumps(ingestor.scan(), indent=2))
        elif args.command == "draft-packs":
            if args.rebuild:
                if not args.pack:
                    parser.error("draft-packs --rebuild requires --pack")
                print(ingestor.drafts.rebuild_approved(args.rebuild, args.pack))
            else:
                print(json.dumps({"drafts": ingestor.draft_files(), "message": "NVIDIA chat must be configured."}, indent=2))
        else:
            from tender.evaluation import evaluate_cases

            report = evaluate_cases(args.cases, gateway, ingestor)
            print(json.dumps(report, indent=2))
            if not report["passed"]:
                repo.engine.dispose()
                raise SystemExit(1)
        repo.engine.dispose()


if __name__ == "__main__":
    main()
