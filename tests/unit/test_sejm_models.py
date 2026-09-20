"""Testy jednostkowe walidacji modeli Pydantic dla Sejm OpenAPI."""

from src.models.sejm_api import (
    SejmAttachmentRaw,
    SejmMPRaw,
    SejmPrintRaw,
    SejmProcessRaw,
    SejmSingleMPVoteRaw,
    SejmVotingRaw,
    VoteType,
)


def test_sejm_process_validation_and_id() -> None:
    """Weryfikuje poprawność modelu SejmProcessRaw oraz właściwości process_id."""
    payload = {
        "number": 42,
        "term": 10,
        "title": "Rządowy projekt ustawy o zmianie podatku od towarów i usług",
        "documentType": "USTAWA",
        "description": "Projekt nowelizacji stawek podatkowych.",
        "author": "Rada Ministrów",
        "authorType": "Rada Ministrów",
        "changeDate": "2024-03-15T14:30:00",
        "prints": [42, "42-A"],
        "stages": [{"stageName": "I czytanie na posiedzeniu Sejmu", "sittingNum": 5}],
    }
    proc = SejmProcessRaw.model_validate(payload)
    assert proc.process_id == "10-42"
    assert proc.document_type == "USTAWA"
    assert len(proc.prints) == 2
    assert len(proc.stages) == 1


def test_sejm_print_validation_and_attachments() -> None:
    """Sprawdza parsowanie druków sejmowych wraz z załącznikami binarnymi."""
    payload = {
        "number": "120",
        "term": 10,
        "title": "Druk nr 120",
        "documentDate": "2024-02-10",
        "attachments": [
            {
                "name": "tekst_projektu.pdf",
                "url": "https://api.sejm.gov.pl/term10/prints/120/120.pdf",
            },
            {"name": "osr.pdf", "url": "https://api.sejm.gov.pl/term10/prints/120/osr.pdf"},
        ],
    }
    p = SejmPrintRaw.model_validate(payload)
    assert p.print_id == "10-120"
    assert len(p.attachments) == 2
    assert isinstance(p.attachments[0], SejmAttachmentRaw)
    assert p.attachments[0].name == "tekst_projektu.pdf"


def test_sejm_single_mp_vote_normalization() -> None:
    """Weryfikuje normalizację głosów posłów do zunifikowanego formatu enum."""
    vote_yes = SejmSingleMPVoteRaw(MP=1, firstLastName="Jan Kowalski", club="KO", vote="ZA")
    vote_no = SejmSingleMPVoteRaw(MP=2, firstLastName="Anna Nowak", club="PiS", vote="PRZECIW")
    vote_abstain = SejmSingleMPVoteRaw(
        MP=3, firstLastName="Piotr Wiśniewski", club="TD", vote="WSTRZYMAŁ SIĘ"
    )
    vote_absent = SejmSingleMPVoteRaw(
        MP=4, firstLastName="Marek Zieliński", club="Lewica", vote="NIEOBECNY"
    )

    assert vote_yes.normalized_vote() == VoteType.YES
    assert vote_no.normalized_vote() == VoteType.NO
    assert vote_abstain.normalized_vote() == VoteType.ABSTAIN
    assert vote_absent.normalized_vote() == VoteType.ABSENT


def test_sejm_voting_validation() -> None:
    """Weryfikuje poprawność modelu SejmVotingRaw."""
    payload = {
        "term": 10,
        "sitting": 8,
        "votingNumber": 15,
        "date": "2024-03-20T18:45:00",
        "title": "Głosowanie nad całością projektu ustawy",
        "totalVoted": 450,
        "yes": 240,
        "no": 200,
        "abstain": 10,
        "votes": [
            {"MP": 1, "firstLastName": "Jan Kowalski", "club": "KO", "vote": "ZA"},
            {"MP": 2, "firstLastName": "Anna Nowak", "club": "PiS", "vote": "PRZECIW"},
        ],
    }
    voting = SejmVotingRaw.model_validate(payload)
    assert voting.voting_id == "10-8-15"
    assert voting.yes == 240
    assert len(voting.votes) == 2


def test_sejm_mp_raw_model() -> None:
    """Weryfikuje poprawność profilu posła."""
    payload = {
        "id": 101,
        "firstLastName": "Jan Kowalski",
        "firstName": "Jan",
        "lastName": "Kowalski",
        "club": "KO",
        "districtName": "Warszawa I",
        "active": True,
    }
    mp = SejmMPRaw.model_validate(payload)
    assert mp.id == 101
    assert mp.club == "KO"
    assert mp.active is True
