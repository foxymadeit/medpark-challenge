# Which local model writes the minutes

The model has to pass every gate below. Published numbers narrow the field;
the bake-off on Kaggle (`minutes/eval/`, never on a team laptop) decides.

## Gates

1. Open weights, runs with no network, under a licence that allows use in a hospital.
2. Fits the challenge's reference hardware: one 16 GB GPU, or a CPU server with 32 GB RAM.
3. Writes native-quality Moldovan Romanian, Russian and English.
4. Reasons well enough to separate decisions from proposals, follow a decision
   reversed later, resolve "I'll do it" to a speaker, and turn "până vineri" into a date.
5. Adds nothing to a grounded summary (low hallucination).
6. Produces valid JSON on request.
7. Holds 32k tokens of context or more (a 60-minute meeting is about 20k tokens).
8. Fast enough for the challenge's 15 minutes from the end of the meeting to the email.

One hardware fact shapes the list. On a CPU, speed follows the *active*
parameters and memory follows the *total*. A mixture-of-experts model with 3
to 4 billion active parameters runs about as fast as a 4B model but carries
the knowledge of a 20 to 30B one, and fits comfortably in 32 GB.

## What published evaluations say

- **Hallucination in grounded summaries**, Vectara leaderboard, 2026
  ([source](https://github.com/vectara/hallucination-leaderboard)): phi-4 3.7%,
  gemma-3-12b 4.4%, qwen3-8b 4.8%, mistral-small-2501 5.1%, gemma-4-26b-a4b 5.2%,
  qwen3-14b 5.4%, qwen3-4b 5.7%, gemma-3-4b 6.4%, gemma-4-31b 7.4%. Higher:
  qwen3.5-35b-a3b 10.5%, qwen3.5-27b 12.1%, gpt-oss-120b 14.2%, ministral-3-14b
  19.4%, ministral-3-8b 21.7%. Thinking variants hallucinate more than their
  plain versions (qwen3-next-80b thinking 9.3%).
- **Romanian grounded tasks**, GMTW-Ro, *Frontiers in AI* 2026
  ([source](https://www.frontiersin.org/journals/artificial-intelligence/articles/10.3389/frai.2026.1831918/full)):
  gpt-oss-20b 79.9%, Llama-3.3-70B 80.0%, Gemma-2-9B 73.3%, RoMistral-7B 68.6%,
  RoGemma2-9B 68.0%, Qwen3-32B 60.2%. The Gemma family and gpt-oss read Romanian
  well; Qwen does worse than its size suggests.
- **Russian**: the MERA leaderboard ([source](https://mera.a-ai.ru/en/text/leaderboard))
  does not list these small models, so we measure Russian ourselves.

## Candidates

| Tier | Model | Size, active | Licence | Why it is here | Concern |
|---|---|---|---|---|---|
| 16 GB GPU | gemma-3-12b-it | 12B dense | Gemma terms (commercial use allowed) | 4.4% hallucination; Gemma strong in Romanian | no thinking mode (we add a reasoning field) |
| 16 GB GPU | gemma-4 dense (12B if released as listed, else 31B at low bits) | 12B dense | Apache 2.0 | newest Gemma, 140+ languages, 128k context | 12B size reported by one source; confirm on Hugging Face |
| 16 GB GPU | phi-4 | 14B dense | MIT | lowest hallucination (3.7%) | trained mainly on English; Romanian and Russian unproven |
| 16 GB GPU | qwen3-14b | 14B dense | Apache 2.0 | 5.4%, thinking mode | Qwen's Romanian scores |
| 16 GB GPU | mistral-small-3.2 | 24B dense | Apache 2.0 | 5.1%, strong Russian | about 14 GB at 4 bits: tight on 16 GB |
| 32 GB CPU | gpt-oss-20b | 21B, 3.6B active | Apache 2.0 | best measured Romanian (79.9%), adjustable reasoning | its 120B sibling hallucinates 14.2%; must be checked |
| 32 GB CPU | gemma-4-26b-a4b | 26B, 4B active | Apache 2.0 | 5.2%, 256k context, Gemma Romanian | about 16 GB at 4 bits |
| 32 GB CPU | qwen3-30b-a3b | 30B, 3B active | Apache 2.0 | thinking mode, fast | Qwen's Romanian scores |
| 32 GB CPU | GigaChat 3 Lightning | 10B, 1.8B active | MIT | Russian-first, very fast | Romanian unknown |
| Specialist writer | EuroLLM-22B-Instruct-2512 | 22B dense | Apache 2.0 | trained for Romanian and Russian among 35 languages | not on the hallucination board |
| Specialist writer | T-Pro 2.0 / T-Lite | 32B / smaller | Apache 2.0 | Russian hybrid reasoning | Russian only |
| Specialist writer | RoGemma2-9B, RoLlama3.1-8B (OpenLLM-Ro) | 8 to 9B | base-model licences | Romanian fine-tunes | below base Gemma-2-9B on GMTW-Ro |
| 8 GB laptop (development only) | gemma-3-4b, gemma-4-E4B, qwen3-4b | about 4B | as above | fit beside the diarizer | too weak for the final product, likely |

**Excluded, with the reason:**
- Aya Expanse: non-commercial licence.
- Llama 3.x 8B: no official Romanian or Russian support.
- Granite 4.0: its 12 languages include neither Romanian nor Russian.
- Ministral 3 (8B, 14B): 19.4 to 21.7% hallucination.
- The qwen3.5 series as the extractor: 10.5 to 12.1% hallucination. It may still be tried as a writer if it is the most fluent.
- Anything larger than the reference hardware.

## The bake-off

It runs on Kaggle (two T4 GPUs as the 16 GB stand-in, plus the CPU for the MoE
tier), on synthetic meetings and published minutes only. It follows the
diarizer's pattern: a smoke test first, a heartbeat every minute, and a failure
report.

For each model we measure:
- extraction accuracy against the gold facts;
- the reasoning traps: reversal, proposal against decision, a conditional decision, a pronoun owner, a relative date;
- facts the verifier has to drop (hallucination before the safety net);
- JSON validity;
- fluency: LanguageTool errors per 100 words in each language, wrong-script and wrong-language sentences, and a blind native rating for Romanian and Russian;
- tokens per second and peak memory.

The winner for each tier goes into the table above, with its numbers.
