# Ilha dos Dois Irmãos, 1778

Módulo para Foundry VTT v14 com a carta náutica de 1778 da ilha que um dia será Gemini City. Feito para o Ato I do evento What-if **A Maldição de Caim**, do Gemini Force Universe (GFU).

## Estado

| Fase | O que entrega | Situação |
| --- | --- | --- |
| 1 | Carta de 1778 (desenho, nomes, referências) | pronta para revisão |
| 2 | Fichas dos locais da Sessão 1 | pronta |
| 3 | Módulo: cena, Notas de Mapa, diário e carta interativa | v0.1.0, em teste |
| 4 | Edição de nomes e descrições no próprio mapa | a fazer |
| 5 | Instalação por link (manifest) | pronta |

## Instalar no Foundry

Em **Configuração → Módulos de complemento → Instalar módulo**, cole no campo **URL do manifesto**:

```
https://github.com/arielcmanussakis-alt/gfu-twin-brothers-1778/releases/latest/download/module.json
```

Ative o módulo no mundo. Na primeira vez, o Mestre recebe uma janela para instalar a carta: ela cria a cena, o diário dos locais com as Notas de Mapa e a macro **Carta de 1778**. O arquivo de segredos do Mestre pode ser escolhido nessa janela ou importado depois em **Configurações → Configurar módulos**.

## O que tem aqui

- `modulo/`: o módulo em si (é o conteúdo do `module.zip` de cada versão).
- `carta/carta-1778.svg`: a carta na visão dos jogadores. Abre em qualquer navegador.
- `ferramentas/carta/`: os scripts que geram a carta a partir da geometria do Atlas de Gemini.

## Segredos do Mestre

Este repositório é público. Os segredos do Ato I (o que cada local esconde, as notas em vermelho e o local H) **não ficam aqui**. Eles vêm num arquivo `.json` à parte, entregue ao Mestre, que o módulo importa para um diário que só o Mestre vê.

## A carta

- Recorte: a costa leste da ilha coberta pelo Atlas de Gemini, com a costa em estado natural (sem aterros, cais ou obras modernas).
- Estilo: carta náutica britânica dos anos 1770, com nomes em português.
- Medidas: profundidades em braças (1,83 m) e escala em léguas marítimas (5,56 km).
- Relevo: hachuras calculadas a partir das curvas de nível do Atlas, com morros e falésias acrescentados onde a cidade moderna apagou o terreno.

## Gerar a carta de novo

Os scripts usam Python com `numpy`, `scipy`, `scikit-image` e `opencv`. A ordem é `extract.py` (lê o Atlas de Gemini), `step1.py` a `step4.py` (terreno), `hach.py` (hachuras) e `build.py` (carta). O arquivo do Atlas não está no repositório, nem o `refs.json` com os segredos que o `build.py` também lê.
