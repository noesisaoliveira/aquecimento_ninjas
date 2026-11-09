# Aquecimento Ninjas – Documentação

Aquecimento por divisão no Home Assistant, com base no **Better Thermostat**.
Até **5 válvulas de radiador (TRV)**, assistente de configuração e painel com gráficos criado automaticamente.

🇬🇧 English: [README.md](../README.md)

---

## Funcionalidades

- **Interruptor geral** – liga/desliga a caldeira e todas as divisões. *Desligado* tem prioridade sobre tudo.
- **Modo Conforto / Eco** – um seletor para a casa toda; cada divisão tem a sua temperatura de conforto e eco.
- **Mudar no termóstato = novo valor** – mudar o objetivo de uma divisão no cartão do termóstato (ou no botão da
  válvula) guarda-o como temperatura de conforto ou eco dessa divisão.
- **Modo ausente** – automático quando todos estão fora durante um tempo configurável, ou manual; usa uma temperatura ausente.
- **Divisões de referência da caldeira** – escolhes que divisões a caldeira lê; com duas ou mais usa a média.
- **Termóstato da caldeira** – usa um existente (ex.: `generic_thermostat`) ou a integração cria um.
- **Notificações** – janelas abertas e bateria fraca.
- **Estatísticas** – média, mínima, máxima, diferença entre divisões, horas/ciclos da caldeira hoje.
- **Painel** – vistas *Aquecimento* e *Gráficos* criadas automaticamente.
- Português e inglês.

## Requisitos

| Requisito | Notas |
|---|---|
| Home Assistant 2025.1 ou mais recente | |
| [HACS](https://hacs.xyz) | Para instalar esta integração e o Better Thermostat |
| **Better Thermostat** (obrigatório) | Um Better Thermostat por divisão |
| Válvulas de radiador (TRV) | Máximo 5 no total, qualquer marca suportada pelo Better Thermostat |
| Um sensor de temperatura por divisão | Usado pelo Better Thermostat e pela referência da caldeira |
| Interruptor ou termóstato da caldeira | Relé que liga a caldeira |

## 1. Instalar o Better Thermostat (obrigatório)

1. **HACS → Integrações →** procura **Better Thermostat** → **Transferir** → reinicia o Home Assistant.
2. **Definições → Dispositivos e serviços → Adicionar integração → Better Thermostat**, uma vez por divisão:
   - **Nome:** a divisão (ex.: `BT_Sala`).
   - **Sensor de temperatura:** o sensor da divisão.
   - **Termóstato (TRV):** a(s) válvula(s) da divisão. Uma divisão com dois radiadores usa **um** Better Thermostat com as duas válvulas.
   - **Sensor de janela:** opcional.
   - **Cooler:** deixa **vazio**. Com um cooler o termóstato passa a ter dois objetivos (aquecer/arrefecer) e o Aquecimento Ninjas não consegue definir a temperatura.
3. Definições avançadas (recomendado):

   | Definição | Valor |
   |---|---|
   | Calibration type | **Offset Based** (se a válvula aceitar correção de temperatura) |
   | Calibration mode | **External Sensor Offset Only** |

## 2. Instalar o Aquecimento Ninjas

### HACS (recomendado)
1. **HACS → ⋮ → Repositórios personalizados** → URL `https://github.com/YOUR_GITHUB_USER/aquecimento_ninjas`, tipo **Integração**.
2. Procura **Aquecimento Ninjas** → **Transferir** → reinicia o Home Assistant.

### Manual
Copia `custom_components/aquecimento_ninjas` para `/config/custom_components/` e reinicia.

## 3. Assistente de configuração

**Definições → Dispositivos e serviços → Adicionar integração → Aquecimento Ninjas**

| Passo | O que escolhes |
|---|---|
| 1. Nome | Nome e termóstato da caldeira: *usar existente* ou *criar* |
| 2. Caldeira | Existente: a entidade climate (+ relé opcional para estatísticas). Criar: o relé, tolerâncias e ciclo mínimo (recomendado 5 min) |
| 3. Divisões | Por divisão: nome, Better Thermostat, as válvulas, sensor da divisão, sensores de bateria e janela (opcionais). Repete até ter todas (máx. 5 válvulas) |
| 4. Presença | Pessoas para o modo ausente, atraso, serviço de notificação (`notify.mobile_app_…`), notificações de janela/bateria |
| 5. Painel | Criar painel e o título |

Para mudar depois: **Definições → Dispositivos e serviços → Aquecimento Ninjas → Configurar**.

### Usar um termóstato de caldeira existente
Define o sensor alvo dele como o sensor **Temperatura de referência** da integração, ex. no `generic_thermostat`:

```yaml
climate:
  - platform: generic_thermostat
    name: Caldeira
    heater: switch.rele_caldeira
    target_sensor: sensor.aquecimento_temperatura_de_referencia   # confirma o ID exato
    min_cycle_duration:
      minutes: 5
```

## Entidades

| Entidade | Função |
|---|---|
| Aquecimento ligado (`switch`) | Interruptor geral |
| Modo (`select`) | Eco / Conforto |
| Modo ausente (`switch`), Temperatura ausente (`number`) | Modo ausente e a sua temperatura |
| `<divisão> conforto`, `<divisão> eco` (`number`) | Temperaturas da divisão |
| `<divisão> usar na caldeira` (`switch`) | Divisão usada na referência da caldeira (por defeito a primeira) |
| Temperatura de referência (`sensor`) | Média das divisões escolhidas → caldeira |
| Temperatura média/mínima/máxima, Diferença mais quente ↔ mais fria | Estatísticas da casa |
| Caldeira ligada hoje, Ciclos da caldeira hoje, Duração média do ciclo | Estatísticas da caldeira |
| Caldeira (`climate`) | Só quando a integração cria o termóstato da caldeira |

Os IDs das entidades dependem do nome escolhido e do idioma do Home Assistant.

## Como funciona

Prioridade (a mais alta primeiro):

1. **Interruptor geral desligado** → caldeira e todas as divisões em *off*. Se alguém voltar a pôr *heat*, é desfeito.
2. **Modo ausente ligado** → todas as divisões na temperatura ausente.
3. **Modo Conforto / Eco** → cada divisão na sua temperatura de conforto / eco.

A integração volta a aplicar os objetivos a cada alteração e a cada 30 minutos, retira os presets do Better Thermostat
(sobrepor-se-iam ao objetivo) e volta a pôr uma divisão em *heat* se o interruptor geral estiver ligado.

## Painel

Criado em `/aquecimento-ninjas` com as vistas **Aquecimento** e **Gráficos**. É um painel normal: podes editá-lo.
- **Recriar** (substitui as alterações): *Configurar → Painel → Recriar*, ou a ação `aquecimento_ninjas.create_dashboard`.
- Mudar as divisões em *Configurar → Divisões* recria-o automaticamente.
- O painel usa APIs internas do Home Assistant. Se uma versão futura as mudar, o aquecimento continua a funcionar e
  fica um aviso no registo; nesse caso cria o painel manualmente.

## Atualizações

O HACS mostra uma atualização quando é publicada uma nova **release no GitHub**. Ver [CHANGELOG.md](../CHANGELOG.md).

## Resolução de problemas

| Problema | Verificar |
|---|---|
| O assistente diz que falta o Better Thermostat | Instala e configura o Better Thermostat primeiro e reinicia |
| Uma divisão mostra dois objetivos (ex.: 16 / 23) | Há um cooler no Better Thermostat dessa divisão → remove-o |
| Uma divisão não segue Conforto/Eco | Interruptor geral ligado? Modo ausente desligado? Ver *Definições → Sistema → Registos* |
| A caldeira nunca liga | Termóstato existente: o sensor alvo é a temperatura de referência? Criado: o relé está certo? |
| Painel em falta | Ver o registo; executar `aquecimento_ninjas.create_dashboard` |

## Recomendação: temperatura da água da caldeira

Numa caldeira de condensação, comece com **55 °C** de temperatura de ida para os radiadores; 50 °C com tempo ameno,
60 °C nos dias mais frios se alguma divisão não chegar ao conforto. Evite 70–80 °C (sem condensação, mais oscilação).

## Licença

[MIT](../LICENSE)
