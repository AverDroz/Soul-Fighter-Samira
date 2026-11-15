# Звук Soul Fighter Samira

Тестовая комната проигрывает оригинальный звук Skin30 на применение Q, W, E, EQ и R. На каждое десятое применение R добавляется одна из трёх русских фраз Самиры, привязанных Riot к этому умению. Другие события тихие для рендера, включая автоатаки, попадания, блоки, выбор цели и отдельные залпы R. Рендерер читает актуальную громкость эффектов из `Options.SFXVolume`, останавливает звук при скрытии игры и не воспроизводит накопившиеся за паузу события.

Варианты R сопоставлены по одинаковым идентификаторам объектов Wwise в английском и русском банках. Английские образцы сверены с записями, где размечены три фразы и отдельный крик. [Список реплик Soul Fighter Samira](https://wiki.leagueoflegends.com/en-us/Samira/Audio#Using_Inferno_Trigger_2)

В `assets/samira-soul-fighter/audio/manifest.json` указаны исходные банки Wwise, события, идентификаторы WEM и SHA-256 исходных банков и извлечённых WAV. SFX взяты из `DATA/FINAL/Champions/Samira.wad.client`, озвучка — из `DATA/FINAL/Champions/Samira.ru_RU.wad.client` той же версии. В русской локали Riot сохранила виртуальные пути банков с `en_US`. Права на исходные материалы принадлежат Riot Games. [Манифест клиента Riot](https://lol.dyn.riotcdn.net/channels/public/releases/6EDAD6B3C9806CB9.manifest)

Для повторного извлечения положи `wwiser.pyz` в `work/asset-research/audio` и распакуй vgmstream в `work/asset-research/audio/vgm`. Звуковые банки и исходные WEM хранятся в рабочей папке. Рендереру нужны только экспортированные WAV и манифест. Во время работы рендерер использует `pygame.mixer` 2.6.1. [wwiser v20260808](https://github.com/bnnm/wwiser/releases/tag/v20260808) · [vgmstream r2168](https://github.com/vgmstream/vgmstream/releases/tag/r2168)

```powershell
$env:PYTHONPATH = 'work/asset-research/deps'
python tools/fetch_samira_audio.py
python src/samira/external/test_samira_audio.py
```

Тест читает контрольные суммы и PCM, а события направляет в имитацию микшера. Отдельная проверка через SDL dummy подтвердила загрузку WAV и остановку каналов без звука.
