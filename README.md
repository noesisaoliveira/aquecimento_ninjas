# Aquecimento Ninjas

Aquecimento por divisão no Home Assistant, com base no **Better Thermostat**.
Até **5 válvulas de radiador (TRV)**, assistente de configuração e painel com gráficos criado automaticamente.

🇬🇧 English: [docs/README.en.md](docs/README.en.md)

---

## Funcionalidades

- **Interruptor geral** – liga/desliga a caldeira e todas as divisões. *Desligado* tem prioridade sobre tudo.
- **Modo Conforto / Eco** – um seletor para a casa toda; cada divisão tem a sua temperatura de conforto e eco.
- **Modo Manual** – no seletor de modo, a temperatura definida no cartão da caldeira passa a ser o objetivo de todas as válvulas, e ligar/desligar a caldeira nesse cartão liga/desliga o aquecimento. Os horários não mudam o modo enquanto estiver em Manual.
- **Mudar no termóstato = novo valor** – mudar o objetivo de uma divisão no cartão do termóstato (ou no botão da
  válvula) guarda-o como temperatura de conforto ou eco dessa divisão.
- **Modo ausente** – automático quando todos estão fora durante um tempo configurável, ou manual; usa uma temperatura ausente.
- **Divisões de referência da caldeira** – escolhes que divisões a caldeira lê; com duas ou mais usa a média.
- **Termóstato da caldeira** – usa um existente (ex.: `generic_thermostat`) ou a integração cria um.
- **Boost** – aquece só as divisões escolhidas até uma temperatura de boost durante 30 min a 6 h; as outras divisões ficam desligadas e no fim tudo é reposto.
- **Emergência** – botão no painel Manutenção que liga o aquecimento sem olhar aos sensores de temperatura: a caldeira fica ligada e as válvulas recebem a temperatura do cartão da caldeira (que podes alterar durante a emergência). Pede o PIN definido em Configurar > Caldeira (4 a 8 dígitos; sem PIN o botão não aparece), termina sozinho ao fim da duração máxima (por omissão 2 h) e bloqueia 5 minutos após 5 PINs errados. Desligar não pede PIN.
- **Janelas** – pausa a divisão 10 s depois de o sensor de janela abrir e retoma 10 s depois de fechar; sem sensor, deteta a janela aberta por uma queda rápida de temperatura.
- **Fiabilidade** – cada comando à válvula é confirmado e reenviado até 3 vezes; se o sensor da divisão falhar, a divisão passa a modo de emergência (temperatura eco).
- **Diagnóstico** – "divisão não aquece", "sensor parado", contagem de comandos falhados e descarga de diagnóstico.
- **Notificações** – janelas abertas, bateria fraca, sensor parado e divisão que não aquece.
- **Estatísticas** – média, mínima, máxima, diferença entre divisões, horas/ciclos da caldeira hoje.
- **Painel** – criado automaticamente: Aquecimento, Horário, Manutenção e Gráficos (estilo Melhorado) ou Aquecimento e Gráficos (estilo Padrão).
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

### Opcional – para o painel Melhorado

Sem estes cartões a integração funciona normalmente e cria o painel Padrão (só cartões do Home Assistant).

| Cartão (HACS → Frontend) | Usado para | Sem ele |
|---|---|---|
| [Mushroom](https://github.com/piitaya/lovelace-mushroom) | Todo o painel Melhorado | É usado o painel Padrão |
| [ApexCharts card](https://github.com/RomRider/apexcharts-card) | Gráfico de temperatura das divisões | O gráfico não aparece |
| [mini-graph-card](https://github.com/kalkih/mini-graph-card) | Gráfico dos sensores de divisão | É usado o gráfico de histórico normal |
| [Scheduler card](https://github.com/nielsfaber/scheduler-card) **+** [Scheduler component](https://github.com/nielsfaber/scheduler-component) (integração) | Vista *Horário* (Conforto/Eco por horário) | A vista não aparece |

Instalar: **HACS → procurar o nome → Transferir** e recarregar o browser (Ctrl+F5). O Scheduler component precisa ainda de
*Definições → Dispositivos e serviços → Adicionar integração → Scheduler* e de reiniciar.
Instala os cartões **antes** de criar o painel, ou recria-o depois (*Configurar → Painel → Recriar*).

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
1. **HACS → ⋮ → Repositórios personalizados** → URL `https://github.com/noesisaoliveira/aquecimento_ninjas`, tipo **Integração**.
2. Procura **Aquecimento Ninjas** → **Transferir** → reinicia o Home Assistant.

### Manual
Copia `custom_components/aquecimento_ninjas` para `/config/custom_components/` e reinicia.

### Já usas a versão YAML (packages + automações)? Remove-a primeiro
A integração faz tudo o que a versão YAML fazia. Se as duas ficarem ativas, **controlam as mesmas válvulas e a caldeira ao mesmo tempo** (temperaturas a mudar sozinhas, boost restaurado duas vezes, caldeira a ligar/desligar fora de horas). Além disso, as entidades da integração ganham o sufixo `_2` porque os IDs já estão ocupados.

Faz uma **cópia de segurança** (*Definições → Sistema → Cópias de segurança*) e, **antes** de adicionar a integração, remove:

| Onde | O que remover |
|---|---|
| `/config/packages/heating.yaml` | O ficheiro inteiro (`input_number`, `input_boolean`, `input_select.aquecimento_modo`, `group.aquecimento_pessoas`, sensores template `aquecimento_*` e `caldeira_*`) |
| `/config/packages/aquecimento_boost_package.yaml` (ou `aquecimento_boost.yaml`) | O ficheiro inteiro (inclui os scripts `aquecimento_boost_iniciar/parar`, o `timer.aquecimento_boost` e as automações `aquecimento_boost_fim` e `aquecimento_boost_guarda`) |
| `/config/automations.yaml` | As automações `aquecimento_aplicar_horarios`, `aquecimento_valvula_para_slider`, `aquecimento_presenca`, `aquecimento_modo_ausente`, `aquecimento_interruptor_geral`, `aquecimento_janela_aberta`, `aquecimento_bateria_fraca` (ou apaga-as em *Definições → Automações*) |
| `/config/scripts.yaml` | O script `aquecimento_configurar_valvulas` |
| `/config/dashboards/aquecimento.yaml` e o painel *Aquecimento* | O painel antigo (*Definições → Painéis*). A integração cria um novo |
| Horários do Scheduler | Os horários que mudam `input_select.aquecimento_modo`. Recria-os depois para o seletor **Modo** da integração |

O **termóstato da caldeira** (`climate` `generic_thermostat` no `configuration.yaml`) tem duas opções:
- **Manter** e escolher *usar existente* no assistente. Nesse caso muda o `target_sensor` para o sensor **Temperatura de referência** da integração (ver [abaixo](#usar-um-termóstato-de-caldeira-existente)).
- **Remover** o bloco e escolher *criar* no assistente, com o mesmo relé (ex.: `switch.kitchen_caldeira`).

**Não removas:** o Better Thermostat, as válvulas, os sensores das divisões, o Zigbee2MQTT nem os outros packages (ex.: `luzes.yaml`). Se a pasta `packages` ficar só com outros ficheiros, mantém a linha `packages: !include_dir_named packages`.

Depois: *Ferramentas de programador → Verificar configuração* → **reiniciar** → em *Definições → Entidades* apaga as entidades antigas `aquecimento_*` / `caldeira_*` que aparecem como *indisponíveis* → só então adiciona a integração.

## 3. Assistente de configuração

**Definições → Dispositivos e serviços → Adicionar integração → Aquecimento Ninjas**

| Passo | O que escolhes |
|---|---|
| 1. Nome | Nome e termóstato da caldeira: *usar existente* ou *criar* |
| 2. Caldeira | Existente: a entidade climate (+ relé opcional para estatísticas). Criar: o relé, tolerâncias e ciclo mínimo (recomendado 5 min); PIN e duração máxima da emergência |
| 3. Divisões | Por divisão: nome, Better Thermostat, as válvulas, sensor da divisão, sensores de bateria e janela (opcionais). Repete até ter todas (máx. 5 válvulas) |
| 4. Presença | Pessoas para o modo ausente, atraso, serviço de notificação (`notify.mobile_app_…`), notificações de janela/bateria |
| 5. Automações | Ativar/desativar aplicação Conforto/Eco, sincronização da válvula, presença, temperatura ausente e interruptor geral; definir a duração máxima do aquecimento; ajustar intervalos e verificações |
| 6. Janelas | Ativar/desativar a pausa e ajustar estabilização, queda de temperatura e duração da pausa |
| 7. Horário | Manter o cartão Scheduler atual ou selecionar uma entidade Schedule existente |
| 8. Painel | Criar painel, o título e o estilo (Automático / Melhorado / Padrão) |

Para mudar depois: **Definições → Dispositivos e serviços → Aquecimento Ninjas → Configurar**.

As opções substituem os controlos das automações YAML `aquecimento_*`:

| Automação YAML | Opção da integração |
|---|---|
| `aquecimento_aplicar_horarios` | **Automações → Aplicar temperaturas Conforto/Eco**; intervalo de reaplicação, confirmação e tentativas das válvulas |
| `aquecimento_valvula_para_slider` | **Automações → Sincronizar alterações do termóstato** |
| `aquecimento_presenca` | **Automações → Ativar modo ausente pela presença**; pessoas e atraso em **Presença e notificações** |
| `aquecimento_modo_ausente` | **Automações → Aplicar a temperatura de ausência** |
| `aquecimento_interruptor_geral` | **Automações → Aplicar o interruptor geral do aquecimento** |
| `aquecimento_janela_aberta` | **Janelas → Pausar o aquecimento**; tempos e queda de temperatura configuráveis. A notificação pode ser desligada em **Presença e notificações** |
| `aquecimento_bateria_fraca` | **Presença e notificações → Notificar bateria fraca**; limite percentual e hora/minuto da verificação diária |

O limite de bateria predefinido é **20%**. Em **Presença e notificações**, também podes desligar notificações de janela, falha do sensor ou divisão que não aquece, sem desligar o controlo do aquecimento.

Em **Horário**, escolhe *Cartão Scheduler (atual)* ou *Entidade Schedule*. Para usar o editor de horários do Home Assistant:

1. Vai a **Definições → Dispositivos e serviços → Auxiliares (Helpers)**.
2. Seleciona **Criar auxiliar → Schedule**.
3. Dá um nome ao horário, por exemplo *Horário do Aquecimento Central*.
4. Na grelha semanal, arrasta sobre os dias e horas em que queres aquecimento em **Conforto**. Podes criar vários blocos e editar um bloco selecionando-o.
5. Seleciona **Criar**. Não são permitidos blocos sobrepostos no mesmo dia nem blocos que atravessem a meia-noite; para esse caso, cria dois blocos consecutivos em dias diferentes.
6. Volta a **Definições → Dispositivos e serviços → Aquecimento Ninjas → Configurar → Horário**, escolhe *Entidade Schedule* e seleciona o helper criado.

Quando o Schedule está ativo, o modo passa a **Conforto**; quando está inativo, passa a **Eco**. A vista Horário do painel mostra a entidade selecionada. Podes alterar os blocos mais tarde em **Auxiliares (Helpers)**.

**Duração máxima do aquecimento:** em **Automações**, define *Duração máxima do aquecimento* (por defeito `0`, desativado). Por exemplo, `2` desliga o interruptor geral após duas horas seguidas ligado. Com *Notificar 10 minutos antes do desligar automático* ativo e um serviço de notificação configurado, recebes um aviso antes de desligar. O limite e o aviso continuam corretos após reiniciar o Home Assistant.

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
| Boost (`switch`), Fim do boost (`sensor`) | Boost ligado/desligado e quando termina |
| `<divisão> janela aberta` (`binary_sensor`) | Divisão em pausa por janela (motivo: sensor ou queda de temperatura) |
| `<divisão> problema no sensor` (`binary_sensor`) | Sensor sem dados há 3 h ou indisponível → modo de emergência |
| `<divisão> não aquece` (`binary_sensor`) | 1 °C ou mais abaixo do objetivo durante 2 h |
| Detetar janela pela queda de temperatura (`switch`) | Liga/desliga a deteção sem sensor de janela |
| Duração do boost, Temperatura do boost (`number`), `<divisão> boost` (`switch`) | Definições e divisões do boost |

Os IDs das entidades dependem do nome escolhido e do idioma do Home Assistant.

## Como funciona

Prioridade (a mais alta primeiro):

1. **Interruptor geral desligado** → caldeira e todas as divisões em *off*. Se alguém voltar a pôr *heat*, é desfeito.
2. **Modo ausente ligado** → todas as divisões na temperatura ausente.
3. **Modo Conforto / Eco** → cada divisão na sua temperatura de conforto / eco.

Ao ligar o interruptor geral, o termóstato da caldeira é definido para a temperatura de conforto (ou eco) **mais alta** entre as divisões. Depois podes alterá-la livremente no termóstato da caldeira; só é redefinida da próxima vez que ligares o aquecimento.

A integração volta a aplicar os objetivos a cada alteração e a cada 30 minutos, retira os presets do Better Thermostat
(sobrepor-se-iam ao objetivo) e volta a pôr uma divisão em *heat* se o interruptor geral estiver ligado.

## Janelas, fiabilidade e diagnóstico

**Janela aberta – pausa e retoma automáticas** (funciona com qualquer válvula):
- *Com sensor de janela:* 10 s aberta → a divisão é desligada; 10 s fechada → volta à temperatura certa.
- *Sem sensor:* se a temperatura da divisão cair 1 °C ou mais em 5 minutos com o aquecimento ligado, a divisão
  fica em pausa. Retoma quando a temperatura deixa de descer (no mínimo 15 min, no máximo 60 min).
  Pode ser desligada com o interruptor *Detetar janela pela queda de temperatura*.

**Comandos confirmados:** depois de cada ordem à válvula, a integração verifica ao fim de 90 s se foi aplicada e
reenvia até 3 vezes. As falhas ficam contadas no atributo `command_failures` de *não aquece*.

**Modo de emergência:** se o sensor de uma divisão ficar indisponível ou sem dados durante 3 h, a divisão
é retirada da média da caldeira e mantida na temperatura eco até o sensor voltar. Se nenhuma divisão
de referência tiver sensor válido, o termóstato da caldeira criado pela integração desliga a caldeira.

**Divisão não aquece:** liga quando a divisão está 1 °C ou mais abaixo do objetivo durante 2 h seguidas
(indica caldeira fraca, radiador mal equilibrado ou válvula presa).

**Descarga de diagnóstico:** *Definições → Dispositivos e serviços → Aquecimento Ninjas → ⋮ → Transferir diagnóstico*.
Inclui a configuração, o estado de cada divisão e as últimas leituras. Junta-o quando abrires um problema no GitHub.

## Boost

Escolhe as divisões (interruptores `<divisão> boost`), a duração e a temperatura, e liga o **Boost** ou usa a ação
`aquecimento_ninjas.start_boost` (opcional `hours`, `temperature`). Durante o boost:
- as divisões escolhidas e a caldeira aquecem até à temperatura de boost; as outras ficam desligadas;
- a caldeira lê só as divisões escolhidas;
- Conforto/Eco, modo ausente e "mudar no termóstato" ficam em pausa.

No fim (ou com `aquecimento_ninjas.stop_boost`) o estado anterior é reposto. Desligar o interruptor geral cancela o boost.
Um boost em curso continua depois de reiniciar o Home Assistant.

## Painel

Criado em `/aquecimento-ninjas`. Dois estilos (*Configurar → Painel → Estilo*):

| Estilo | Vistas | Requer |
|---|---|---|
| **Melhorado** | Aquecimento (com Boost), Horário\*, Manutenção, Gráficos | [Mushroom](https://github.com/piitaya/lovelace-mushroom). Opcional: [ApexCharts](https://github.com/RomRider/apexcharts-card), [mini-graph](https://github.com/kalkih/mini-graph-card), [Scheduler card](https://github.com/nielsfaber/scheduler-card) + componente Scheduler |
| **Padrão** | Aquecimento, Gráficos | Nada (cartões do Home Assistant) |
| **Automático** (por omissão) | Melhorado se o Mushroom estiver instalado, senão Padrão | |

\* Com *Cartão Scheduler*, a vista só aparece quando o cartão e a integração Scheduler estão instalados. Com *Entidade Schedule*, a vista mostra o helper selecionado e não requer o cartão Scheduler.

É um painel normal: podes editá-lo.
- **Recriar** (substitui as alterações): *Configurar → Painel → Recriar*, ou a ação `aquecimento_ninjas.create_dashboard`.
- Mudar as divisões em *Configurar → Divisões* recria-o automaticamente.
- O painel usa APIs internas do Home Assistant. Se uma versão futura as mudar, o aquecimento continua a funcionar e
  fica um aviso no registo; nesse caso cria o painel manualmente.

## Atualizações

O HACS mostra uma atualização quando é publicada uma nova versão (*release*) no GitHub. Ver [CHANGELOG.md](CHANGELOG.md).

## Resolução de problemas

| Problema | Verificar |
|---|---|
| O assistente diz que falta o Better Thermostat | Instala e configura o Better Thermostat primeiro e reinicia |
| Uma divisão mostra dois objetivos (ex.: 16 / 23) | Há um cooler no Better Thermostat dessa divisão → remove-o |
| Uma divisão não segue Conforto/Eco | Interruptor geral ligado? Modo ausente desligado? Ver *Definições → Sistema → Registos* |
| A caldeira nunca liga | Termóstato existente: o sensor alvo é a temperatura de referência? Criado: o relé está certo? |
| Painel em falta | Ver o registo; executar `aquecimento_ninjas.create_dashboard` |
| Uma divisão pára sem motivo | Ver *janela aberta* (motivo `temperature`): desliga *Detetar janela pela queda de temperatura* se acontecer com correntes de ar |
| Divisão em temperatura eco no modo Conforto | *Problema no sensor* ligado: o sensor da divisão não envia dados (bateria, alcance) |

## Recomendação: temperatura da água da caldeira

Numa caldeira de condensação, começa com **55 °C** de temperatura de ida para os radiadores; 50 °C com tempo ameno,
60 °C nos dias mais frios se alguma divisão não chegar ao conforto. Evita 70–80 °C (sem condensação, mais oscilação).

## Para quem mantém o projeto – publicar uma versão

1. Aumenta a `version` em `custom_components/aquecimento_ninjas/manifest.json` **e** a `VERSION` em `const.py`.
2. Acrescenta as alterações ao `CHANGELOG.md`.
3. Faz commit e cria uma *release* no GitHub com a tag `vX.Y.Z` (a mesma versão). O workflow *Release check* confirma-o.

## Licença

[MIT](LICENSE)
