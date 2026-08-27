"""Testes que rodam sem internet."""
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app import db, main
from app.extractor import HeuristicExtractor, LLMExtractor, escolher_extrator
from app.fetcher import extrair_texto

HTML = """
<html><head><title>Acme Tecnologia | Solucoes</title></head>
<body><nav>menu</nav><script>x=1</script>
<p>A Acme Tecnologia desenvolve plataformas de automacao industrial para
industrias de medio porte, com foco em reducao de custo operacional.</p>
<p>Fundada em 2015, atende mais de 200 clientes em todo o Brasil e mantem
operacao propria de suporte tecnico especializado.</p>
<footer>contato@acme.com.br (11) 98888-7777</footer></body></html>
"""

def test_extrair_texto_remove_script_e_pega_titulo():
    titulo, texto = extrair_texto(HTML)
    assert titulo == "Acme Tecnologia | Solucoes"
    assert "x=1" not in texto
    assert "automacao industrial" in texto

def test_heuristico_monta_briefing():
    titulo, texto = extrair_texto(HTML)
    b = HeuristicExtractor().extrair("https://acme.com.br", titulo, texto)
    assert b.empresa == "Acme Tecnologia"
    assert "automacao" in b.resumo
    assert b.confianca == "baixa"

def test_heuristico_encontra_contatos():
    titulo, texto = extrair_texto(HTML)
    b = HeuristicExtractor().extrair("https://acme.com.br", titulo, texto)
    assert "contato@acme.com.br" in b.contatos

def test_escolher_extrator_sem_chave_devolve_heuristico(monkeypatch):
    # Trava L-05: sem chave de API no ambiente, o sistema roda no heuristico.
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    assert isinstance(escolher_extrator(), HeuristicExtractor)

def test_escolher_extrator_com_chave_devolve_llm(monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "chave-de-teste-sem-valor")
    assert isinstance(escolher_extrator(), LLMExtractor)

def test_extrator_que_falha_nao_derruba_a_requisicao(monkeypatch):
    class ExtratorQuebrado:
        nome = "llm"

        def extrair(self, url, titulo, texto):
            raise RuntimeError("provedor fora do ar")

    monkeypatch.setattr(main, "escolher_extrator", lambda: ExtratorQuebrado())
    monkeypatch.setattr(main, "buscar_html", lambda url: HTML)
    monkeypatch.setattr(db, "salvar", lambda *args, **kwargs: datetime.now(timezone.utc))
    monkeypatch.setattr(db, "buscar", lambda *args, **kwargs: None)

    # Sem "with": nao dispara o lifespan, entao nao chama db.criar_tabelas()
    # nem cria o arquivo briefings.db.
    client = TestClient(main.app)
    resp = client.post(
        "/api/briefings",
        json={"urls": ["https://acme.com.br"], "forcar_atualizacao": True},
    )

    assert resp.status_code == 200
    dados = resp.json()
    assert len(dados) == 1
    item = dados[0]
    assert item["extrator"] == "heuristico"
    assert item["briefing"]["confianca"] == "baixa"
    assert item["origem"] == "novo"
    # D-05/D-06: a degradacao viaja num campo proprio, com mensagem curta,
    # sem vazar o texto da excecao original (que nao e LLMError aqui).
    assert item["degradado"].startswith("IA indisponivel")
    assert "provedor fora do ar" not in item["degradado"]

def test_llm_sem_chave_levanta_erro_claro(monkeypatch):
    # SPEC S14: sem chave, o erro precisa ser claro para o vendedor, nao um
    # traceback. D-12 teste 4.
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    with pytest.raises(RuntimeError) as exc:
        LLMExtractor().extrair("https://acme.com.br", "Acme Tecnologia", "texto qualquer")

    assert "chave" in str(exc.value).lower()
    assert "None" not in str(exc.value) and "NoneType" not in str(exc.value)

def test_falha_ao_salvar_no_cache_nao_derruba_o_lote(monkeypatch):
    # L-02: falha de gravacao no cache e falha de otimizacao, nao motivo para
    # descartar um briefing ja gerado com sucesso, nem para derrubar outras
    # URLs do mesmo lote que ja tinham sido processadas.
    monkeypatch.delenv("LLM_API_KEY", raising=False)

    def salvar_com_falha_seletiva(url, briefing, extrator):
        if "quebra" in url:
            raise RuntimeError("disco cheio")
        return datetime.now(timezone.utc)

    monkeypatch.setattr(main, "buscar_html", lambda url: HTML)
    monkeypatch.setattr(db, "buscar", lambda *args, **kwargs: None)
    monkeypatch.setattr(db, "salvar", salvar_com_falha_seletiva)

    # Sem "with": nao dispara o lifespan, entao nao chama db.criar_tabelas()
    # nem cria o arquivo briefings.db.
    client = TestClient(main.app)
    resp = client.post(
        "/api/briefings",
        json={
            "urls": [
                "https://acme.com.br/quebra",
                "https://acme.com.br/boa",
            ],
            "forcar_atualizacao": True,
        },
    )

    assert resp.status_code == 200
    dados = resp.json()
    assert len(dados) == 2

    # A segunda URL, que gravou com sucesso, segue intacta.
    item_boa = dados[1]
    assert item_boa["extrator"] == "heuristico"
    assert item_boa["origem"] == "novo"
    assert item_boa["briefing"]["empresa"] == "Acme Tecnologia"

    # A primeira URL preserva o briefing ja gerado, so sinalizando a
    # degradacao no campo proprio, sem vazar o texto da excecao original.
    item_quebrada = dados[0]
    assert item_quebrada["extrator"] == "heuristico"
    assert item_quebrada["briefing"]["empresa"] == "Acme Tecnologia"
    assert item_quebrada["degradado"] == main.AVISO_CACHE_INDISPONIVEL

