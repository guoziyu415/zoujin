# 校对表：走れメロス（hashire-merosu@1.0.0-draft.3）

由 `packages/worldsim/reference/review_sheet.py` 从 `world.json` 生成，**不要手改**；改 `world.src.json` 后重新生成。
引文后的数字是规范化原文的段落号。校对人在最后一列填 OK / 改 / 删。〔推断〕= 原文没写、由人推断。

## 1. 锚点（PM 确认：这些不能被玩家改变）

| ID | 内容 | 原文 | 校对 |
|---|---|---|---|
| beat.01 | 未明、村を発つ：メロスは未明に村を出て、十里の道を市へ向かう。 | 「きょう未明メロスは村を出発し」(1) | |
| beat.02 | 市の異変：買い物を終え大路を歩くうち、日が落ちた市がやけに寂しいことに気づく。 | 「歩いているうちにメロスは、まちの様子を怪しく思った。」(1) | |
| beat.12 | 大雨：宣誓のころ黒雲が空を覆い、車軸を流すような大雨になる。雨は翌朝まで続く。 | 「黒雲が空を覆い、ぽつりぽつり雨が降り出し」(32) | |
| beat.15 | 雨が上がる：朝のうちに雨が止み、日が高く昇って暑くなる。 | 「雨も止み、日は高く昇って、そろそろ暑くなって来た。」(38) | |
| beat.17 | 濁流、橋が流される：前日の豪雨で水源地が氾濫し、橋は流され、繋ぎ舟もない。 | 「猛勢一挙に橋を破壊し」(38) | |
| fact.melos-shepherd | メロスは村の牧人である。 | 「メロスは、村の牧人である。」(1) | |
| fact.melos-family | メロスには父母も妻もなく、十六の妹と二人暮しである。 | 「メロスには父も、母も無い。女房も無い。」(1) | |
| fact.sister-engaged | 妹の花婿は、村の律気な一牧人である。 | 「この妹は、村の或る律気な一牧人を、近々、花婿として迎える事になっていた。」(1) | |
| fact.melos-errand | メロスは花嫁の衣裳と祝宴の御馳走を買いに市へ来た。 | 「花嫁の衣裳やら祝宴の御馳走やらを買いに」(1) | |
| fact.friendship | メロスとセリヌンティウスは竹馬の友で、二年会っていなかった。 | 「メロスには竹馬の友があった。」(1)<br>「二年ぶりで相逢うた。」(26) | |
| fact.selinuntius-stonemason | セリヌンティウスはシラクスの市で石工をしている。 | 「今は此のシラクスの市で、石工をしている。」(1) | |
| fact.city-silent | シラクスの市は夜でもひっそりして、やけに寂しい。二年前は賑やかだった。 | 「市全体が、やけに寂しい。」(1) | |
| fact.king-killings | 王は妹婿、世嗣、妹、妹の子、皇后、賢臣アレキスを殺した。 | 「はい、はじめは王様の妹婿さまを。」(6)<br>「それから、賢臣のアレキス様を。」(6)<br>「悪心を抱いている、というのですが」(4) | |
| fact.king-distrust | 王は乱心ではなく、人を信ずることができないのだという。 | 「いいえ、乱心ではございませぬ。人を、信ずる事が出来ぬ、というのです。」(8) | |
| fact.hostage-decree | 王は派手な暮しの臣下に人質を一人ずつ差し出させ、拒めば十字架にかける。 | 「少しく派手な暮しをしている者には、人質ひとりずつ差し出すことを命じて居ります。」(8) | |
| fact.six-killed-today | 王の命令で、一日のうちに六人が殺された。 | 「きょうは、六人殺されました。」(8) | |
| fact.groom-wanted-wait | 花婿は仕度ができていないので葡萄の季節まで待ちたかった。 | 「こちらには未だ何の仕度も出来ていない、葡萄の季節まで待ってくれ」(32) | |

## 2. 节拍

| ID | 时间（原著 / 最早〜最晚） | 地点 | 人物 | 类型 | 前提 | 结果 | 原文 | 校对 |
|---|---|---|---|---|---|---|---|---|
| beat.01 未明、村を発つ | D0 04:00（D0 03:00〜D0 05:00） | village | メロス | anchor | — | — | 「きょう未明メロスは村を出発し」(1) | |
| beat.02 市の異変 | D0 19:10（D0 19:00〜D0 20:00） | syracuse-square | メロス | anchor | — | — | 「歩いているうちにメロスは、まちの様子を怪しく思った。」(1) | |
| beat.03 王の暴虐を知る | D0 19:30（D0 19:10〜D0 21:00） | syracuse-square | メロス、市の若い衆、市の老爺 | mutable | — | melos.knowsTyranny = True | 「王様は、人を殺します。」(2)<br>「聞いて、メロスは激怒した。」(9) | |
| beat.04 王城で捕縛 | D0 20:00（D0 19:30〜D0 22:00） | execution-ground | メロス、城の警吏 | mutable | melos.knowsTyranny == True | melos.custody = arrested、melos → castle、item.dagger 被拿走 | 「買い物を、背負ったままで、のそのそ王城にはいって行った。」(10)<br>「調べられて、メロスの懐中からは短剣が出て来たので、騒ぎが大きくなってしまった。」(10) | |
| beat.05 王との問答と約束 | D0 20:30（D0 20:00〜D0 23:00） | castle | メロス、王ディオニス | mutable | melos.custody == arrested | promise.made = True、hostage.who = char.selinuntius | 「処刑までに三日間の日限を与えて下さい。」(18)<br>「あれを、人質としてここに置いて行こう。」(20)<br>「願いを、聞いた。その身代りを呼ぶがよい。」(22)<br>「メロスは口惜しく、地団駄踏んだ。」(25) | |
| beat.06 深夜、友が召される | D0 23:30（D0 21:30〜D1 01:00） | castle | セリヌンティウス、メロス、王ディオニス | mutable | promise.made == True | hostage.fate = held、selinuntius → castle | 「竹馬の友、セリヌンティウスは、深夜、王城に召された。」(26) | |
| beat.07 満天の星の下を発つ | D0 23:45（D0 21:40〜D1 02:00） | castle | メロス | mutable | hostage.fate == held | melos.custody = on-parole、melos.stamina -30 | 「メロスは、すぐに出発した。初夏、満天の星である。」(26) | |
| beat.08 村に着き、婚礼を告げる | D1 10:00（D1 07:00〜D1 14:00） | melos-home | メロス、メロスの妹 | mutable | melos.custody == on-parole | melos → melos-home、wedding.status = scheduled | 「村へ到着したのは、翌る日の午前」(27)<br>「あす、おまえの結婚式を挙げる。」(28)<br>「村の人たちに知らせて来い。結婚式は、あすだと。」(30) | |
| beat.09 支度をして眠る | D1 10:30（D1 10:00〜D1 20:00） | melos-home | メロス | mutable | — | melos.stamina +35 | 「間もなく床に倒れ伏し、呼吸もせぬくらいの深い眠りに落ちてしまった。」(31) | |
| beat.10 花婿を夜通し説く | D2 04:30（D1 20:00〜D2 08:00） | groom-house | メロス、花婿 | mutable | wedding.status == scheduled | groom.agreed = True、melos.stamina -10 | 「眼が覚めたのは夜だった。」(32)<br>「夜明けまで議論をつづけて、やっと、どうにか婿をなだめ、すかして、説き伏せた。」(32) | |
| beat.11 真昼の婚礼 | D2 12:00（D2 07:00〜D2 18:40） | melos-home | メロス、メロスの妹、花婿 | mutable | groom.agreed == True | wedding.status = held | 「結婚式は、真昼に行われた。」(32) | |
| beat.12 大雨 | D2 12:30（D2 12:20〜D2 13:00） | village | — | anchor | — | weather = storm | 「黒雲が空を覆い、ぽつりぽつり雨が降り出し」(32) | |
| beat.13 祝宴と別れの言葉 | D2 21:00（D2 13:40〜D2 23:40） | melos-home | メロス、メロスの妹、花婿 | mutable | wedding.status == held | — | 「メロスは、一生このままここにいたい、と思った。」(32)<br>「もう一つ、メロスの弟になったことを誇ってくれ。」(35) | |
| beat.14 薄明、雨中を走り出る | D3 04:30（D3 01:20〜D3 09:40） | melos-home | メロス | mutable | melos.custody == on-parole | melos.stamina +30、melos → village | 「眼が覚めたのは翌る日の薄明の頃である。」(37)<br>「雨中、矢の如く走り出た。」(37) | |
| beat.17 濁流、橋が流される | D3 06:00（D3 04:40〜D3 08:00） | river | — | anchor | — | bridge = destroyed | 「猛勢一挙に橋を破壊し」(38) | |
| beat.15 雨が上がる | D3 09:00（D3 08:00〜D3 10:00） | neighbor-village | — | anchor | — | weather = after-rain | 「雨も止み、日は高く昇って、そろそろ暑くなって来た。」(38) | |
| beat.16 気を緩めて歩く | D3 09:40（D3 05:40〜D3 19:00） | neighbor-village | メロス | mutable | — | melos.stamina -15 | 「ゆっくり歩こう、と持ちまえの呑気さを取り返し、好きな小歌をいい声で歌い出した。」(38) | |
| beat.18 激流を泳ぎ切る | D3 12:00（D3 08:00〜D3 19:00） | river | メロス | mutable | bridge == destroyed | river.crossing = swam、melos.stamina -35 | 「太陽も既に真昼時です。」(38)<br>「メロスは、ざんぶと流れに飛び込み」(39) | |
| beat.19 峠の山賊 | D3 14:00（D3 10:00〜D3 19:00） | mountain-pass | メロス、峠の山賊 | mutable | — | bandits = defeated、melos.stamina -25 | 「陽は既に西に傾きかけている。」(39)<br>「たちまち、三人を殴り倒し」(47) | |
| beat.20 力尽きる | D3 15:00（D3 11:00〜D3 19:00） | spring | メロス | mutable | melos.stamina <= 20 | melos.resolve -60、melos.doubted = True | 「ついに、がくりと膝を折った。」(47)<br>「四肢を投げ出して、うとうと、まどろんでしまった。」(47)<br>「ああ、もういっそ、悪徳者として生き伸びてやろうか。」(47) | |
| beat.s2 ちらと友を疑う | D3 16:00（D3 14:00〜D3 17:50） | castle | セリヌンティウス | mutable | hostage.who == char.selinuntius、hostage.fate == held、selinuntius.faith <= 2〔推断〕 | selinuntius.doubted = True | 「私はこの三日の間、たった一度だけ、ちらと君を疑った。」(65) | |
| beat.21 泉 | D3 16:30（D3 12:30〜D3 19:00） | spring | メロス | mutable | — | melos.stamina +30、melos.resolve = 100 | 「水を両手で掬って、一くち飲んだ。」(48)<br>「走れ！　メロス。」(48)<br>「先刻の、あの悪魔の囁きは、あれは夢だ。」(49) | |
| beat.22 黒い風のように | D3 17:30（D3 13:30〜D3 19:00） | road-to-city | メロス、旅の一団 | mutable | — | melos.clothing = nearly-naked | 「メロスは黒い風のように走った。」(50)<br>「メロスは、いまは、ほとんど全裸体であった。」(50) | |
| beat.s1 刑場に引き出される友 | D3 18:00（D3 17:00〜D3 18:55） | execution-ground | セリヌンティウス、王ディオニス、市の群衆、城の警吏 | mutable | hostage.fate == held | hostage.fate = on-cross、selinuntius → execution-ground、maiden → execution-ground、king → execution-ground、crowd → execution-ground、guards → execution-ground | 「王様が、さんざんあの方をからかっても、メロスは来ます、とだけ答え」(57) | |
| beat.23 フィロストラトス | D3 18:30（D3 14:30〜D3 19:00） | road-to-city | メロス、フィロストラトス | mutable | — | — | 「もう、駄目でございます。」(53)<br>「それだから、走るのだ。信じられているから走るのだ。」(58)<br>「いや、まだ陽は沈まぬ。」(56) | |
| beat.24 日没、刑場へ | D3 19:00（D3 16:00〜D3 19:00） | execution-ground | メロス、セリヌンティウス、市の群衆、城の警吏 | mutable | melos.custody == on-parole | melos.custody = returned、hostage.fate = released、melos → execution-ground | 「メロスは疾風の如く刑場に突入した。間に合った。」(60)<br>「セリヌンティウスの縄は、ほどかれたのである。」(62) | |
| beat.25 殴り合いと抱擁 | D3 19:05（D3 16:00〜D3 20:00） | execution-ground | メロス、セリヌンティウス | mutable | hostage.fate == released、hostage.who == char.selinuntius〔推断〕 | — | 「私を殴れ。ちから一ぱいに頬を殴れ。」(63)<br>「「ありがとう、友よ。」二人同時に言い」(67)<br>「刑場一ぱいに鳴り響くほど音高くメロスの右頬を殴った。」(64)<br>「メロスは腕に唸りをつけてセリヌンティウスの頬を殴った。」(66) | |
| ↳ 变体 beat.25.v-neither〔推断〕 | — | — | — | — | melos.doubted == False、selinuntius.doubted == False | どちらも相手を疑わなかった。殴り合うことはなく、二人は「ありがとう、友よ」と言って抱き合い、声を放って泣く。  | 「「ありがとう、友よ。」二人同時に言い」(67) | |
| ↳ 变体 beat.25.v-melos-only〔推断〕 | — | — | — | — | selinuntius.doubted == False | メロスだけが途中の悪い夢を打ち明け、セリヌンティウスに殴られる。セリヌンティウスは一度も疑わなかったと言い、殴られないまま二人は抱き合う。  | 「私は、途中で一度、悪い夢を見た。」(63) | |
| ↳ 变体 beat.25.v-selinuntius-only〔推断〕 | — | — | — | — | melos.doubted == False | メロスは道中で一度も約束を投げ出しかけなかった。セリヌンティウスだけが一度疑ったことを打ち明けて殴られ、二人は抱き合う。  | 「私はこの三日の間、たった一度だけ、ちらと君を疑った。」(65) | |
| beat.26 王の改心 | D3 19:15（D3 16:00〜D3 20:00） | execution-ground | 王ディオニス、メロス、セリヌンティウス、市の群衆 | mutable | hostage.fate == released、king.trust >= 1〔推断〕、king.disposition != reformed〔推断〕 | king.disposition = reformed、king.trust = 80 | 「信実とは、決して空虚な妄想ではなかった。」(69)<br>「万歳、王様万歳。」(71)<br>「どっと群衆の間に、歓声が起った。」(70) | |
| beat.27 緋のマント | D3 19:20（D3 16:00〜D3 20:00） | execution-ground | 市の少女、メロス、セリヌンティウス | mutable | melos.custody == returned | melos.clothing = scarlet-cloak | 「ひとりの少女が、緋のマントをメロスに捧げた。」(72)<br>「勇者は、ひどく赤面した。」(74) | |

## 3. 事实

| ID | 陈述 | 何时成立 | 公开 | 原文 | 校对 |
|---|---|---|---|---|---|
| fact.melos-shepherd | メロスは村の牧人である。 | pre | public | 「メロスは、村の牧人である。」(1) | |
| fact.melos-family | メロスには父母も妻もなく、十六の妹と二人暮しである。 | pre | private | 「メロスには父も、母も無い。女房も無い。」(1) | |
| fact.sister-engaged | 妹の花婿は、村の律気な一牧人である。 | pre | private | 「この妹は、村の或る律気な一牧人を、近々、花婿として迎える事になっていた。」(1) | |
| fact.melos-errand | メロスは花嫁の衣裳と祝宴の御馳走を買いに市へ来た。 | pre | private | 「花嫁の衣裳やら祝宴の御馳走やらを買いに」(1) | |
| fact.friendship | メロスとセリヌンティウスは竹馬の友で、二年会っていなかった。 | pre | private | 「メロスには竹馬の友があった。」(1)<br>「二年ぶりで相逢うた。」(26) | |
| fact.selinuntius-stonemason | セリヌンティウスはシラクスの市で石工をしている。 | pre | public | 「今は此のシラクスの市で、石工をしている。」(1) | |
| fact.city-silent | シラクスの市は夜でもひっそりして、やけに寂しい。二年前は賑やかだった。 | pre | public | 「市全体が、やけに寂しい。」(1) | |
| fact.king-killings | 王は妹婿、世嗣、妹、妹の子、皇后、賢臣アレキスを殺した。 | pre | private | 「はい、はじめは王様の妹婿さまを。」(6)<br>「それから、賢臣のアレキス様を。」(6)<br>「悪心を抱いている、というのですが」(4) | |
| fact.king-distrust | 王は乱心ではなく、人を信ずることができないのだという。 | pre | private | 「いいえ、乱心ではございませぬ。人を、信ずる事が出来ぬ、というのです。」(8) | |
| fact.hostage-decree | 王は派手な暮しの臣下に人質を一人ずつ差し出させ、拒めば十字架にかける。 | pre | private | 「少しく派手な暮しをしている者には、人質ひとりずつ差し出すことを命じて居ります。」(8) | |
| fact.six-killed-today | 王の命令で、一日のうちに六人が殺された。 | pre | private | 「きょうは、六人殺されました。」(8) | |
| fact.melos-dagger | メロスは短剣を懐に王城へ入り、警吏に捕らえられた。 | beat.04 | public | 「メロスの懐中からは短剣が出て来たので」(10) | |
| fact.melos-reason | メロスは妹に亭主を持たせるため、三日の猶予を願った。 | beat.05 | public | 「たった一人の妹に、亭主を持たせてやりたいのです。」(18) | |
| fact.promise | 王はメロスに三日目の日没までに戻れと命じ、遅れたら身代りを殺すと言った。身代りはセリヌンティウス。 | beat.05 | public | 「三日目には日没までに帰って来い。おくれたら、その身代りを、きっと殺すぞ。」(22) | |
| fact.king-whisper | 王はメロスに「ちょっとおくれて来い、そうすれば罪をゆるす」とささやいた。 | beat.05 | private | 「ちょっとおくれて来るがいい。おまえの罪は、永遠にゆるしてやろうぞ。」(22)<br>「王は私に、ちょっとおくれて来い、と耳打ちした。」(47)<br>「おまえの心は、わかっているぞ。」(24) | |
| fact.king-intent | 王はメロスが帰らないと決めつけ、身代りを殺して「人は信じられぬ」と見せつけるつもりでいる。 | beat.05 | private | 「どうせ帰って来ないにきまっている。」(21) | |
| fact.selinuntius-hostage | セリヌンティウスは深夜王城に召され、身代りとして縄打たれた。 | beat.06 | public | 「セリヌンティウスは、縄打たれた。」(26) | |
| fact.wedding-tomorrow | メロスは妹に、婚礼をあすにすると告げた（理由は話していない）。 | beat.08 | public | 「あす、おまえの結婚式を挙げる。」(28)<br>「「なんでも無い。」メロスは無理に笑おうと努めた。」(28) | |
| fact.groom-agreed | 花婿は夜明けに、婚礼をその日の真昼に挙げることを承知した。 | beat.10 | public | 「やっと、どうにか婿をなだめ、すかして、説き伏せた。」(32)<br>「結婚式は、真昼に行われた。」(32) | |
| fact.groom-wanted-wait | 花婿は仕度ができていないので葡萄の季節まで待ちたかった。 | pre | private | 「こちらには未だ何の仕度も出来ていない、葡萄の季節まで待ってくれ」(32) | |
| fact.wedding-held | 婚礼は真昼に行われた。 | beat.11 | public | 「結婚式は、真昼に行われた。」(32) | |
| fact.storm | 婚礼の宣誓のころから車軸を流すような大雨になった。 | beat.12 | public | 「やがて車軸を流すような大雨となった。」(32) | |
| fact.melos-farewell | メロスは祝宴で妹と花婿に、眼が覚めたらすぐ市へ出かける、大切な用事があると告げた（何の用か、いつ戻るかは言っていない）。 | beat.13 | public | 「眼が覚めたら、すぐに市に出かける。大切な用事があるのだ。」(33) | |
| fact.bridge-destroyed | 前日の豪雨で川が氾濫し、橋が流された。 | beat.17 | public | 「きのうの豪雨で山の水源地は氾濫し」(38)<br>「猛勢一挙に橋を破壊し」(38) | |
| fact.no-boats | 繋ぎ舟はすべて浪にさらわれ、渡し守もいない。 | beat.17 | public | 「繋舟は残らず浪に浚われて影なく、渡守りの姿も見えない。」(38) | |
| fact.bandits-ambush | 峠で一隊の山賊が待ち伏せている。 | beat.19 | public | 「突然、目の前に一隊の山賊が躍り出た。」(39) | |
| fact.melos-suspects-king | メロスは山賊を王の差し金だと考えた。 | beat.19 | private | 「さては、王の命令で、ここで私を待ち伏せしていたのだな。」(45) | |
| fact.melos-despair | メロスは力尽きて倒れ、一度は約束を投げ出そうと思った（「悪い夢」）。 | beat.20 | private | 「ああ、もういっそ、悪徳者として生き伸びてやろうか。」(47)<br>「私は、途中で一度、悪い夢を見た。」(63) | |
| fact.travelers-rumor | 旅の一団は、身代りの男がいまごろ磔にかかっていると噂した。 | beat.22 | public | 「いまごろは、あの男も、磔にかかっているよ。」(50) | |
| fact.execution-crowd | 日没に、市の石工が刑場で磔にされることになっていて、広場の一角の刑場に人が集まりはじめている。 | beat.22 | public | 「すでに磔の柱が高々と立てられ、縄を打たれたセリヌンティウスは、徐々に釣り上げられてゆく。」(61)<br>「大声で刑場の群衆にむかって叫んだ」(61) | |
| fact.selinuntius-steadfast | セリヌンティウスは刑場に引き出され、王にからかわれても「メロスは来ます」とだけ答えた。 | beat.s1 | public | 「刑場に引き出されても、平気でいました。」(57) | |
| fact.selinuntius-doubted-once | セリヌンティウスは三日の間に一度だけメロスを疑った。 | beat.s2 | private | 「私はこの三日の間、たった一度だけ、ちらと君を疑った。」(65) | |

## 4. 人物

### メロス（char.melos）· 可对话

村の牧人。十六の内気な妹と二人暮らし。政治はわからないが、邪悪には人一倍敏感。

| 项 | 内容 | 原文 | 校对 |
|---|---|---|---|
| 性格 | 政治がわからない | 「メロスには政治がわからぬ。」(1) | |
| 性格 | 邪悪に人一倍敏感 | 「けれども邪悪に対しては、人一倍に敏感であった。」(1) | |
| 性格 | 単純で、思い立ったらすぐ動く | 「メロスは、単純な男であった。」(10) | |
| 性格 | 呑気なところがある | 「持ちまえの呑気さを取り返し」(38) | |
| 性格 | 人を疑う事と嘘をつく事が一番きらい | 「おまえの兄の、一ばんきらいなものは、人を疑う事と、それから、嘘をつく事だ。」(33) | |
| 性格 | 未練の情もある | 「メロスほどの男にも、やはり未練の情というものは在る。」(32) | |
| 性格 | 死を覚悟しても命乞いはしない | 「命乞いなど決してしない。」(18) | |
| 动机 | 妹に亭主を持たせる（婚礼を挙げる）〔until beat.11〕 | 「たった一人の妹に、亭主を持たせてやりたいのです。」(18) | |
| 动机 | 婚礼の品を買いそろえて村へ帰る。婚礼は近いが、日取りはまだ決まっていない〔until beat.08〕 | 「結婚式も間近かなのである。」(1)<br>「花嫁の衣裳やら祝宴の御馳走やらを買いに」(1) | |
| 动机 | 約束どおり戻り、身代りの友を救う〔since beat.05〕〔until beat.24〕 | 「身代りの友を救う為に走るのだ。」(38) | |
| 动机 | 王に人の信実を見せる〔since beat.05〕〔until beat.26〕 | 「あの王に、人の信実の存するところを見せてやろう。」(37) | |
| 动机 | 市を暴君の手から救う〔since beat.03〕〔until beat.26〕 | 「市を暴君の手から救うのだ。」(12) | |
| 说话 | 一人称「私」；率直で激しい。古風な断定（〜ぬ、〜のだ）。目上にも物怖じしない。；开局在做：idle | 「人の心を疑うのは、最も恥ずべき悪徳だ。」(14)<br>「そうです。帰って来るのです。」(20)〔since beat.05〕<br>「いや、まだ陽は沈まぬ。」(54)〔since beat.23〕<br>「信じられているから走るのだ。」(58)〔since beat.23〕<br>「私にはいのちの他には何も無い。」(43)〔since beat.19〕<br>「私は信頼されている。私は信頼されている。」(49)〔since beat.21〕<br>「私は、途中で一度、悪い夢を見た。」(63)〔since beat.25〕〔条件 melos.doubted == True〕 | |
| 知道 | melos-shepherd@pre、melos-family@pre、sister-engaged@pre、melos-errand@pre、friendship@pre、selinuntius-stonemason@pre、city-silent@beat.02、king-killings@beat.03、king-distrust@beat.03、hostage-decree@beat.03、six-killed-today@beat.03、melos-dagger@beat.04、promise@beat.05、melos-reason@beat.05、king-whisper@beat.05、selinuntius-hostage@beat.06、wedding-tomorrow@beat.08、groom-wanted-wait@beat.10、wedding-held@beat.11、storm@beat.12、melos-farewell@beat.13、bridge-destroyed@beat.17、no-boats@beat.17、bandits-ambush@beat.19、melos-suspects-king@beat.19、melos-despair@beat.20、travelers-rumor@beat.22、selinuntius-steadfast@beat.23、selinuntius-doubted-once@beat.25、groom-agreed@beat.10 | — | |
| 他能为你 | 水をくれた牧童を覚えていて、三日のうちに戻るという約束を初めて話し、家まで連れて行く〔开局互助：role.shepherd-boy〕〔推断〕 | 「三日のうちに」(18) | |
| 你能为他 | よろめいて村に戻ったメロスに水を一杯差し出す〔开局互助：role.shepherd-boy〕〔推断〕 | 「よろめいて歩いて来る兄の、疲労困憊の姿を見つけて驚いた。」(27) | |
| 他能为你 | 王の前で、あなたのことを口にする（条件：melos.custody == arrested）〔大事：兑现时算关键时刻〕〔推断〕 | — | |
| 他能为你 | 同行を許す〔推断〕 | — | |
| 你能为他 | 花婿を説き伏せるのを手伝う〔推断〕 | 「婿の牧人も頑強であった。」(32) | |
| 你能为他 | 近道や浅瀬を教える〔推断〕 | — | |
| 你能为他 | 市へ先に走り、もうすぐ着くと知らせる〔推断〕 | — | |
| 约定 | メロス：「必ず戻る」 | 「必ず、ここへ帰って来ます」(18) | |
| 约定 | 玩家：「セリヌンティウスに伝える」〔推断〕 | — | |
| 打算 act.1 | 王の暴虐を聞き、王城へ乗り込む | 「呆れた王だ。生かして置けぬ。」(9) | |
| 打算 act.2 | 夜通し村へ急ぐ | 「一睡もせず十里の路を急ぎに急いで」(27) | |
| 打算 act.3 | 婚礼を急がせ、済んだら一眠りして発つ | 「ちょっと一眠りして、それからすぐに出発しよう」(32) | |
| 打算 act.4 | 日没までに刑場へ走る | 「走れ！　メロス。」(48) | |

### 王ディオニス（char.king）· 可对话

シラクスの王。これまでに身内や臣下を次々に殺してきた。

| 项 | 内容 | 原文 | 校对 |
|---|---|---|---|
| 性格 | 人を信じることができない〔until beat.26〕 | 「人を、信ずる事が出来ぬ、というのです。」(8) | |
| 性格 | 静かで威厳がある。顔は蒼白で眉間の皺が深い | 「その王の顔は蒼白で、眉間の皺は、刻み込まれたように深かった。」(11) | |
| 性格 | 孤独を抱えている | 「おまえには、わしの孤独がわからぬ。」(13) | |
| 性格 | 残虐で、人を試して嘲る〔until beat.26〕 | 「それを聞いて王は、残虐な気持で、そっと北叟笑んだ。」(21) | |
| 性格 | 本当は平和を望んでいると言う | 「わしだって、平和を望んでいるのだが。」(15) | |
| 性格 | 人の腹の底が見えると思い込んでいる | 「わしには、人の腹綿の奥底が見え透いてならぬ。」(17) | |
| 动机 | 人は信じられないと世に見せつける〔until beat.26〕 | 「世の中の、正直者とかいう奴輩にうんと見せつけてやりたいものさ。」(21) | |
| 说话 | 一人称「わし」；低く静か。相手を「おまえ」と呼ぶ。冷笑的で、ときに嘆息する。；开局在做：idle | 「人の心は、あてにならない。人間は、もともと私慾のかたまりさ。信じては、ならぬ。」(15)<br>「逃がした小鳥が帰って来るというのか。」(19)〔since beat.05〕<br>「ちょっとおくれて来るがいい。」(22)〔since beat.05〕<br>「どうか、わしをも仲間に入れてくれまいか。」(69)〔since beat.26〕<br>「だまれ、下賤の者。」(17)<br>「いのちが大事だったら、おくれて来い。」(24)〔since beat.05〕 | |
| 设计台词 | 「ならば、おまえも人質になるか。」〔since beat.04〕〔until beat.06〕〔条件 melos.custody == arrested〕〔推断〕（見知らぬ旅人がメロスを保証した時の冷笑（UX 校対 1.2）。受ければ第 1 類「あなたが身代わりになった」への道。取り返しがつかないので意図確認（S-054 ③）を通す） | — | |
| 知道 | king-killings@pre、king-distrust@pre、hostage-decree@pre、six-killed-today@pre、melos-dagger@beat.04、promise@beat.05、melos-reason@beat.05、king-whisper@beat.05、king-intent@beat.05、selinuntius-hostage@beat.06、friendship@beat.06、selinuntius-steadfast@beat.s1 | — | |
| 他能为你 | 人を信じられなくなったわけを語る〔推断〕 | 「おまえには、わしの孤独がわからぬ。」(13) | |
| 他能为你 | 人質に一度だけ会わせる〔大事：兑现时算关键时刻〕〔推断〕 | — | |
| 你能为他 | 本当のことを言って聞かせる〔效果：king.trust +10〕〔推断〕 | 「人の心は、あてにならない。」(15) | |
| 你能为他 | 群臣の前で王の面目をつぶさない〔效果：king.trust +5〕〔推断〕 | — | |
| 约定 | 王ディオニス：「あの男が戻ったら、おまえの言うことも聞いてやろう」（冷笑しながらの賭け。あの男は戻らないと確信しているから言う。軟化として演じない（UX 校対 2.4、評測 E3））〔推断〕 | — | |
| 打算 act.1 | メロスを試し、身代りを磔にして世の正直者に見せつけるつもりでいる | 「見せつけてやりたいものさ」(21) | |
| 打算 act.2 | 城で人質を見張らせ、眠れずにいる〔推断〕 | — | |
| 打算 act.3 | メロスは戻らぬと決めつけ、処刑の支度をさせる〔推断〕 | — | |
| 打算 act.4 | 日没に刑場で身代りを処刑する | 「刑場に引き出されても、平気でいました。」(57) | |

### セリヌンティウス（char.selinuntius）· 可对话

メロスの竹馬の友。シラクスの市の石工。

| 项 | 内容 | 原文 | 校对 |
|---|---|---|---|
| 性格 | 多くを語らず、友を信じる | 「セリヌンティウスは無言で首肯き、メロスをひしと抱きしめた。」(26) | |
| 性格 | 刑場でも動じない強い信念〔since beat.s1〕 | 「メロスは来ます、とだけ答え、強い信念を持ちつづけている様子でございました。」(57) | |
| 性格 | 三日の間に一度だけ友を疑った〔since beat.25〕〔条件 selinuntius.doubted == True〕 | 「私はこの三日の間、たった一度だけ、ちらと君を疑った。」(65) | |
| 性格 | 気がきく | 「佳き友は、気をきかせて教えてやった。」(72) | |
| 动机 | 友を信じて待つ〔since beat.06〕〔until beat.24〕 | 「あの方は、あなたを信じて居りました。」(57) | |
| 说话 | 一人称「私」；穏やかで簡潔。メロスを「君」と呼ぶ。；开局在做：work | 「生れて、はじめて君を疑った。」(65)〔since beat.25〕〔条件 selinuntius.doubted == True〕<br>「君が私を殴ってくれなければ、私は君と抱擁できない。」(65)〔since beat.25〕〔条件 selinuntius.doubted == True〕<br>「メロス、君は、まっぱだかじゃないか。」(73)〔since beat.27〕 | |
| 设计台词 | 「手を止めるな。日が落ちる前に、ここまでは刻んでおきたい。」〔until beat.02〕〔推断〕（第一幕、日没（19:00）までの工房で弟子に（ux-design 5.1）。市は前からひっそりしているので、捕縛の前に騒がしさは口にしない（UX 校対 7.1）） 依据 「ひっそりしている。」(1)<br>「……城の方が、やけに騒がしいな。」〔since beat.04〕〔until beat.06〕〔推断〕（メロスが捕まったあと、召される前（UX 校対 7.1）） 依据 「騒ぎが大きくなってしまった」(10)<br>「……メロスは来る。それだけだ。」〔since beat.06〕〔until beat.24〕〔推断〕（人質の夜。多くを語らない。王や警吏に向かっては原文どおり「メロスは来ます。」（UX 校対 7.1）） 依据 「メロスは来ます、とだけ答え」(57)<br>「……陽が、傾いてきたな。」〔since beat.s2〕〔until beat.24〕〔条件 selinuntius.doubted == True〕〔推断〕（ちらと疑ったあと。疑ったことは口にしない（打ち明けるのは刑場で、メロスにだけ））<br>「メロス、私は一度も君を疑わなかった。……ひとりで待っていたのでは、なかったからな。」〔since beat.25〕〔条件 selinuntius.doubted == False、selinuntius.attended == True〕〔推断〕（S-064：疑わなかった局の刑場（beat.25.v-melos-only / v-neither）。原作どおり「メロス、」で始め「私」「君」。v-melos-only で言い返しに聞こえないよう陳述にする（UX 校対 7.1）。後半が本当になるよう、弟子がそばにいた局に限る） | — | |
| 知道 | friendship@pre、selinuntius-stonemason@pre、king-killings@pre、king-distrust@pre、hostage-decree@pre、promise@beat.06、melos-reason@beat.06、selinuntius-hostage@beat.06、melos-errand@beat.06、melos-dagger@beat.06、selinuntius-doubted-once@beat.s2、melos-despair@beat.25 | — | |
| 他能为你 | 深夜に召される前に、工房とあとのことを弟子に託す〔开局互助：role.apprentice〕〔推断〕 | 「竹馬の友、セリヌンティウスは、深夜、王城に召された。」(26) | |
| 你能为他 | 親方の留守、工房を守ると約束する〔开局互助：role.apprentice〕〔推断〕 | — | |
| 他能为你 | 城と王の様子を教える〔推断〕 | — | |
| 他能为你 | 第一幕の深夜、警吏が工房へ親方を召しに来て弟子（または居合わせた旅人）を問い詰めた時、前に立ってかばう（条件：promise.made == True、hostage.fate == none）〔大事：兑现时算关键时刻〕〔推断〕 | — | |
| 你能为他 | 人質の夜、そばにいる〔推断〕 | — | |
| 你能为他 | 自分の目で見た、あるいは確かに聞いたメロスの様子を届ける（根拠のない励ましは keep-faith の方）（条件：hostage.who == char.selinuntius、hostage.fate == held）〔效果：selinuntius.faith +1〕〔推断〕 | — | |
| 你能为他 | メロスは必ず戻ると、親方と一緒に信じ続ける（条件：hostage.who == char.selinuntius、hostage.fate == held）〔效果：selinuntius.faith +1〕〔推断〕 | 「メロスは来ます、とだけ答え」(57) | |
| 约定 | 玩家：「工房を守る」〔推断〕 | — | |
| 约定 | 玩家：「そばにいる」〔推断〕 | — | |
| 打算 act.1 | 工房で石を刻み、召されれば黙って応じる | 「セリヌンティウスは無言で首肯き」(26) | |
| 打算 act.2 | 城で縄を打たれたまま、メロスを信じて待つ | 「メロスは来ます、とだけ答え」(57) | |
| 打算 act.3 | 城で縄を打たれたまま、メロスを信じて待つ | 「メロスは来ます、とだけ答え」(57) | |
| 打算 act.4 | 刑場に引き出されても平然としている | 「刑場に引き出されても、平気でいました。」(57) | |

### メロスの妹（char.sister）· 可对话

メロスの妹。十六の内気な娘で、兄と二人で村に暮らしている。

| 项 | 内容 | 原文 | 校对 |
|---|---|---|---|
| 性格 | 十六歳、内気 | 「十六の、内気な妹と二人暮しだ。」(1) | |
| 性格 | 結婚を喜び、恥じらう | 「妹は頬をあからめた。」(29) | |
| 性格 | 兄を心配する | 「そうして、うるさく兄に質問を浴びせた。」(27) | |
| 性格 | 兄の言葉に夢見心地でうなずく〔since beat.13〕 | 「花嫁は、夢見心地で首肯いた。」(34) | |
| 动机 | 結婚する〔until beat.11〕 | 「花婿として迎える事になっていた。」(1) | |
| 动机 | 婚礼は近いが、日取りはまだ決まっていない〔until beat.08〕 | 「結婚式も間近かなのである。」(1) | |
| 说话 | 一人称「わたし」；控えめで丁寧な話し方（〜です、〜ます）。兄を「兄さん」と呼ぶ。口数が少なく、照れると言葉が途切れる。；开局在做：work | — | |
| 知道 | melos-family@pre、sister-engaged@pre、melos-errand@pre、wedding-tomorrow@beat.08、wedding-held@beat.11、storm@beat.12、melos-farewell@beat.13 | — | |
| 他能为你 | 兄にあなたを引き合わせる〔推断〕 | — | |
| 他能为你 | 兄の出発のとき、あなたにも弁当を持たせる〔交给你：item.provisions〕〔推断〕 | — | |
| 你能为他 | 婚礼の支度を手伝う〔推断〕 | 「神々の祭壇を飾り」(31) | |
| 你能为他 | 兄が去ったあと、そばにいる〔推断〕 | — | |
| 约定 | 玩家：「兄さんを見届ける」〔推断〕 | — | |
| 打算 act.3 | 兄の代りに羊の番をし、婚礼の支度をする | 「メロスの十六の妹も、きょうは兄の代りに羊群の番をしていた。」(27) | |
| 打算 act.4 | 花婿と新しい暮らしを始める〔推断〕 | — | |

### 花婿（char.groom）· 可对话

村の律気な牧人。メロスの妹の結婚相手。

| 项 | 内容 | 原文 | 校对 |
|---|---|---|---|
| 性格 | 律気 | 「村の或る律気な一牧人」(1) | |
| 性格 | 頑強に譲らない〔until beat.10〕 | 「婿の牧人も頑強であった。」(32) | |
| 性格 | 照れ屋 | 「花婿は揉み手して、てれていた。」(36) | |
| 动机 | 仕度を整え、葡萄の季節に婚礼を挙げたい〔until beat.10〕 | 「葡萄の季節まで待ってくれ」(32) | |
| 说话 | 一人称「わたし」；実直で慎重な話し方（〜です、〜ます）。メロスを「メロスさん」と呼ぶ。；开局在做：work | 「こちらには未だ何の仕度も出来ていない」(32) | |
| 知道 | sister-engaged@pre、melos-family@pre、groom-wanted-wait@pre、wedding-held@beat.11、storm@beat.12、melos-farewell@beat.13、groom-agreed@beat.10 | — | |
| 他能为你 | あなたが支度を手伝ったか、自分の口で頼んだから、婚礼を早めることに同意する（メロスの説得だけで承知したなら、あなたのためとは数えない）（条件：wedding.status == scheduled）〔大事：兑现时算关键时刻〕〔推断〕 | 「やっと、どうにか婿をなだめ、すかして、説き伏せた。」(32) | |
| 他能为你 | 灯や上着を貸す〔交给你：item.lantern〕〔推断〕 | — | |
| 他能为你 | 牧人だけが知る、峠の脇道と町へ抜ける野道を教える〔效果：player.knowsShortcut = True〕〔推断〕 | — | |
| 你能为他 | 婚礼の支度を手伝う〔推断〕 | 「こちらには未だ何の仕度も出来ていない」(32) | |
| 约定 | 花婿：「妹さんを大切にする」〔推断〕 | — | |
| 打算 act.3 | 支度ができるまで、葡萄の季節まで婚礼を待ちたい | 「葡萄の季節まで待ってくれ」(32) | |

### フィロストラトス（char.philostratus）· 可对话

セリヌンティウスの弟子の若い石工。

| 项 | 内容 | 原文 | 校对 |
|---|---|---|---|
| 性格 | セリヌンティウスの弟子の若い石工 | 「貴方のお友達セリヌンティウス様の弟子でございます。」(53)<br>「その若い石工も」(53) | |
| 性格 | 師を慕い、メロスを恨みつつも命を案じる〔since beat.23〕 | 「おうらみ申します。」(55)<br>「いまはご自分のお命が大事です。」(57) | |
| 动机 | 師を救いたかった。今はメロスの命を守りたい〔since beat.23〕 | 「いまはご自分のお命が大事です。」(57) | |
| 说话 | 一人称「わたくし」；丁寧（〜でございます、〜居りました）。取り乱しやすい。；开局在做：work | 「もう、駄目でございます。」(53)〔since beat.23〕<br>「ああ、あなたは遅かった。」(55)〔since beat.23〕<br>「ひょっとしたら、間に合わぬものでもない。」(59)〔since beat.23〕 | |
| 知道 | selinuntius-stonemason@pre、king-killings@pre、hostage-decree@pre、selinuntius-hostage@beat.06、promise@beat.06、selinuntius-steadfast@beat.s1 | — | |
| 他能为你 | 刑場の今の様子を教える〔推断〕 | 「刑場に引き出されても、平気でいました。」(57) | |
| 他能为你 | 刑場へ先に走って伝言を届ける〔大事：兑现时算关键时刻〕〔推断〕 | — | |
| 你能为他 | 道中のメロスの様子を伝える〔推断〕 | — | |
| 约定 | 玩家：「メロスは来る」 | 「メロスは来ます、とだけ答え」(57) | |
| 打算 act.1 | 工房で親方の帰りを待つ〔推断〕 | — | |
| 打算 act.2 | 城の門の外で、親方の様子をうかがっている〔推断〕 | — | |
| 打算 act.3 | 城の門の外で、親方の様子をうかがっている〔推断〕 | — | |
| 打算 act.4 | 刑場から走り出て、メロスを止めようとする | 「その若い石工も、メロスの後について走りながら叫んだ。」(53) | |

### 市の老爺（char.old-man）· 可对话

シラクスの市に住む老人。王の所業を知っていて、怯えている。

| 项 | 内容 | 原文 | 校对 |
|---|---|---|---|
| 性格 | 人目をはばかり、怯えている | 「老爺は、あたりをはばかる低声で、わずか答えた。」(1) | |
| 动机 | 目をつけられずに生き延びる | 「老爺は答えなかった。」(1) | |
| 说话 | 一人称「—」；へりくだった丁寧語（〜ます、〜居りませぬ、〜ございませぬ）。年寄りらしい語尾（〜くだされ、〜ですぞ、〜なされ）も使う。；开局在做：idle | 「王様は、人を殺します。」(2)<br>「いいえ、乱心ではございませぬ。」(8)<br>「誰もそんな、悪心を持っては居りませぬ。」(4) | |
| 设计台词 | 「旅の方、日が落ちますぞ。早う宿へお入りなされ。」〔until beat.07〕〔推断〕（第一幕の夕方（ux-design 16.2 の予録台詞））<br>「旅の方、暗うなる前に、すまぬが家の前まで手を貸してくだされ。」〔until beat.07〕〔推断〕（S-044 ② の開口例：老爺の方から旅人に頼む（aid.old-man.listen）） | — | |
| 知道 | king-killings@pre、king-distrust@pre、hostage-decree@pre、six-killed-today@pre、city-silent@pre、execution-crowd@beat.22 | — | |
| 你能为他 | 怯える老爺の話を最後まで聞き、暗くなる道を家まで送る〔开局互助：role.traveler〕〔效果：player.walkedOldManHome = True〕〔推断〕 | 「老爺は、あたりをはばかる低声で、わずか答えた。」(1) | |
| 他能为你 | 声をひそめて王の所業を打ち明け、メロスが来たら引き合わせる〔开局互助：role.traveler〕〔推断〕 | 「王様は、人を殺します。」(2) | |
| 他能为你 | 警吏に目をつけられない道を教える〔推断〕 | — | |
| 你能为他 | 聞いたことを誰にも言わない〔推断〕 | — | |
| 约定 | 玩家：「誰にも言わない」〔推断〕 | — | |
| 打算 act.1 | 日が落ちる前に家へ帰り、王の噂には口をつぐむ〔推断〕 | 「老爺は、あたりをはばかる低声で、わずか答えた。」(1) | |

### 市の若い衆（char.young-man）

シラクスの市の若い衆。

| 项 | 内容 | 原文 | 校对 |
|---|---|---|---|
| 性格 | 恐れて口を閉ざす | 「若い衆は、首を振って答えなかった。」(1) | |
| 动机 | 関わり合いを避ける | 「若い衆は、首を振って答えなかった。」(1) | |
| 说话 | 一人称「—」；口が重く、ぶっきらぼうな話し方。；开局在做：idle | — | |
| 知道 | king-killings@pre、hostage-decree@pre、city-silent@pre、execution-crowd@beat.22 | — | |

### 城の警吏（char.guards）

王城を巡邏する役人たち。王の命令で人を捕らえ、刑場で磔を執り行う。

| 项 | 内容 | 原文 | 校对 |
|---|---|---|---|
| 性格 | 王の命令に従う | 「たちまち彼は、巡邏の警吏に捕縛された。」(10) | |
| 动机 | 命令を遂行する | 「私だ、刑吏！」(62) | |
| 说话 | 一人称「—」；役人らしく、短く命令口調の話し方。；开局在做：idle | — | |
| 知道 | hostage-decree@pre、melos-dagger@beat.04、promise@beat.05、selinuntius-hostage@beat.06 | — | |

### 峠の山賊（char.bandits）

棍棒を持った一隊の山賊。

| 项 | 内容 | 原文 | 校对 |
|---|---|---|---|
| 性格 | 棍棒で襲う | 「山賊たちは、ものも言わず一斉に棍棒を振り挙げた。」(46) | |
| 动机 | メロスの持ち物と命を奪う | 「その、いのちが欲しいのだ。」(44) | |
| 说话 | 一人称「—」；粗野。；开局在做：idle | 「どっこい放さぬ。持ちもの全部を置いて行け。」(42) | |
| 知道 | — | — | |

### 旅の一団（char.travelers）

街道を行く旅の一団。

| 项 | 内容 | 原文 | 校对 |
|---|---|---|---|
| 性格 | 噂話をする | 「一団の旅人と颯っとすれちがった瞬間」(50) | |
| 说话 | 一人称「—」；くだけた口調。；开局在做：idle | 「いまごろは、あの男も、磔にかかっているよ。」(50) | |
| 知道 | selinuntius-hostage@beat.06 | — | |

### 市の群衆（char.crowd）

シラクスの市の人々。

| 项 | 内容 | 原文 | 校对 |
|---|---|---|---|
| 性格 | 感情の振れ幅が大きい | 「群衆は、どよめいた。」(62) | |
| 说话 | 一人称「—」；叫び。；开局在做：absent | 「万歳、王様万歳。」(71) | |
| 知道 | selinuntius-steadfast@beat.s1、execution-crowd@beat.22 | — | |

### 市の少女（char.maiden）

シラクスの市の少女。

| 项 | 内容 | 原文 | 校对 |
|---|---|---|---|
| 性格 | メロスの裸体を人に見られるのを口惜しがる〔since beat.27〕 | 「この可愛い娘さんは、メロスの裸体を、皆に見られるのが、たまらなく口惜しいのだ。」(73) | |
| 说话 | 一人称「—」；素朴で、言葉少なな話し方。；开局在做：absent | — | |
| 知道 | — | — | |

## 5. 因果边

| ID | 关系 | 说明 | 推断 | 原文 | 校对 |
|---|---|---|---|---|---|
| edge.03-04 | beat.03 —enables→ beat.04 | 暴虐を聞いて激怒し、単純なメロスはそのまま王城に入る |  | 「呆れた王だ。生かして置けぬ。」(9) | |
| edge.04-05 | beat.04 —enables→ beat.05 | 捕縛されて王の前に引き出されたから問答になる |  | 「メロスは、王の前に引き出された。」(10) | |
| edge.05-06 | beat.05 —enables→ beat.06 | 王が身代りを呼べと言ったから友が召される |  | 「その身代りを呼ぶがよい。」(22) | |
| edge.06-07 | beat.06 —requires→ beat.07 | 身代りが縄打たれてはじめてメロスは放免される | 〔推断〕 | 「セリヌンティウスは、縄打たれた。メロスは、すぐに出発した。」(26) | |
| edge.07-08 | beat.07 —enables→ beat.08 | 夜通し十里を歩いて翌日午前に村に着く |  | 「メロスはその夜、一睡もせず十里の路を急ぎに急いで」(27) | |
| edge.08-10 | beat.08 —enables→ beat.10 | あす婚礼と決めたので花婿を説く必要がある | 〔推断〕 | — | |
| edge.10-11 | beat.10 —requires→ beat.11 | 花婿の同意がなければ婚礼は挙げられない |  | 「説き伏せた。結婚式は、真昼に行われた。」(32) | |
| edge.11-13 | beat.11 —enables→ beat.13 | 婚礼のあとの祝宴 |  | 「祝宴は、夜に入っていよいよ乱れ華やかになり」(32) | |
| edge.13-14 | beat.13 —enables→ beat.14 | 一眠りしてから発つと決める |  | 「ちょっと一眠りして、それからすぐに出発しよう、と考えた。」(32) | |
| edge.12-17 | beat.12 —enables→ beat.17 | 前日の豪雨で川が氾濫し橋が流される |  | 「きのうの豪雨で山の水源地は氾濫し」(38) | |
| edge.17-18 | beat.17 —requires（只管先后）→ beat.18 | 橋も舟もないので泳ぐしかない。洪水は朝に起きて橋はもう無い。メロスが早く着いても遅く着いても泳ぐしかないので、時間はずらさない（timeLink: order） |  | 「泳ぎ切るより他に無い。」(39) | |
| edge.18-20 | beat.18 —enables（只管先后）→ beat.20 | 泳ぎと格闘と炎天で疲れ果てる。激流で体力を使ったことが倒れる原因（体力は var.melos.stamina で運ぶ）。時刻は峠（edge.19-20）だけで決まるので、この辺は先後だけ（峠で早く片づけば、そのぶん早く倒れる） |  | 「流石に疲労し」(47) | |
| edge.19-20 | beat.19 —enables→ beat.20 | 山賊との格闘で体力を使う |  | 「一気に峠を駈け降りたが、流石に疲労し」(47) | |
| edge.21-24 | beat.21 —enables（只管先后）→ beat.24 | 泉で甦らなければ刑場に着けない。時間は泉の後の道（beat.22、beat.23）を通って伝わるので、このエッジは先後だけを決める（timeLink: order。shift のままだと、町への道で稼いだ分が泉の 0 偏移に止められて刑場まで届かない） |  | 「歩ける。行こう。」(48) | |
| edge.24-25 | beat.24 —requires→ beat.25 | 間に合って縄がほどかれたから二人は向き合える |  | 「セリヌンティウスの縄は、ほどかれたのである。」(62) | |
| edge.25-26 | beat.25 —enables→ beat.26 | 二人の様を見て王の心が動く |  | 「暴君ディオニスは、群衆の背後から二人の様を、まじまじと見つめていたが」(68) | |
| edge.24-27 | beat.24 —enables→ beat.27 | ほとんど裸で走り着いたから少女がマントを捧げる |  | 「メロス、君は、まっぱだかじゃないか。」(73) | |
| edge.14-16 | beat.14 —enables→ beat.16 | 帰り道の順序（原文の記述順）。前の節拍が遅れれば、この節拍も同じだけ遅れる | 〔推断〕 | — | |
| edge.16-18 | beat.16 —enables→ beat.18 | 帰り道の順序（原文の記述順）。前の節拍が遅れれば、この節拍も同じだけ遅れる | 〔推断〕 | — | |
| edge.18-19 | beat.18 —enables→ beat.19 | 帰り道の順序（原文の記述順）。前の節拍が遅れれば、この節拍も同じだけ遅れる | 〔推断〕 | — | |
| edge.20-21 | beat.20 —enables→ beat.21 | 帰り道の順序（原文の記述順）。前の節拍が遅れれば、この節拍も同じだけ遅れる | 〔推断〕 | — | |
| edge.21-22 | beat.21 —enables→ beat.22 | 帰り道の順序（原文の記述順）。前の節拍が遅れれば、この節拍も同じだけ遅れる | 〔推断〕 | — | |
| edge.22-23 | beat.22 —enables→ beat.23 | 帰り道の順序（原文の記述順）。前の節拍が遅れれば、この節拍も同じだけ遅れる | 〔推断〕 | — | |
| edge.23-24 | beat.23 —enables→ beat.24 | 帰り道の順序（原文の記述順）。前の節拍が遅れれば、この節拍も同じだけ遅れる | 〔推断〕 | — | |
| edge.16-18-delay | beat.16 —delays（40 分）→ beat.18 | のんびり歩いた分だけ川に着くのが遅れる。メロスがのんびり歩かなければ、40 分早く川に着く（分数は推断）。急いでも同じ道なので体力の消耗は変わらない | 〔推断〕 | — | |
| edge.20-21-delay | beat.20 —delays（60 分）→ beat.21 | 力尽きて草原にまどろんだ分だけ泉で起き上がるのが遅れる。倒れなければ 60 分早く泉に着く（分数は推定） | 〔推断〕 | 「四肢を投げ出して、うとうと、まどろんでしまった。」(47) | |

## 6. 设计层（全部〔推断〕，UX / PM 确认）

### 地点与场景

| 地点 | 场景 | 相邻（分钟） | 说明 | 校对 |
|---|---|---|---|---|
| place.village メロスの村 | scene.village | melos-home 5、groom-house 10、neighbor-village 120 |  | |
| place.melos-home メロスの家と羊小屋 | scene.village | village 5 |  | |
| place.groom-house 花婿の家 | scene.village | village 10 |  | |
| place.neighbor-village 隣村 | （无场景） | village 120、river 180 | 第一版に場面はない。ここを通る移動と、ここで起きる節拍（beat.15、beat.16）は叙事者の語りで伝える。 | |
| place.river 川と橋 | scene.road-river | neighbor-village 180、mountain-pass 100 |  | |
| place.mountain-pass 峠 | scene.road-pass | river 100、spring 45 |  | |
| place.spring 峠下の草原と泉 | scene.road-spring | mountain-pass 45、road-to-city 120 |  | |
| place.road-to-city 市へ続く野の道 | scene.road-field | spring 120、syracuse-square 60 |  | |
| place.syracuse-square シラクスの広場と大路 | scene.syracuse-square | road-to-city 60、castle 10、stonemason-workshop 2、execution-ground 2 |  | |
| place.castle 王城 | scene.castle-throne | syracuse-square 10、execution-ground 5 |  | |
| place.execution-ground 刑場 | scene.syracuse-square | castle 5、syracuse-square 2 |  | |
| place.stonemason-workshop セリヌンティウスの石工の仕事場 | scene.syracuse-square | syracuse-square 2 |  | |

### 身份

| ID | 名字 | 版本 | 起点 | 认识 | 能进 | 有条件能进 | 说明 | 校对 |
|---|---|---|---|---|---|---|---|---|
| role.traveler | 旅人 | 第 1 版 | act.1 · syracuse-square · D0 17:30 | — | syracuse-square、stonemason-workshop、execution-ground | castle：player.companionOf == char.melos、melos.custody == arrested<br>castle：player.custody == arrested<br>castle：player.companionOf == char.selinuntius | 誰も知らない。最初のプレイ向け（S-002）。王城にはメロスの連れとして連れて行かれた時に入れる（縛られない、UX 5.1）。 | |
| role.apprentice | 石屋の弟子 | 第 1 版 | act.1 · stonemason-workshop · D0 17:30 | セリヌンティウス、フィロストラトス | stonemason-workshop、syracuse-square、execution-ground | castle：player.companionOf == char.selinuntius | 原文ではフィロストラトスが「セリヌンティウスの弟子の若い石工」。重複を避けるため、フィロストラトスの弟弟子とする（UX 5.1 は「セリヌンティウス親方の工房で、石を刻んでいる」）。 | |
| role.castle-maid | 王城の侍女 | 第 2 版 | act.1 · castle · D0 17:30 | 王ディオニス、城の警吏 | castle、execution-ground、syracuse-square | — | 王の耳打ち（fact.king-whisper）を立ち聞きできる唯一の身分。 | |
| role.shepherd-boy | 村の牧童 | 第 1 版 | act.3 · village · D1 09:00 | メロス、メロスの妹、花婿 | village、melos-home、groom-house、neighbor-village、river、mountain-pass、spring、road-to-city、syracuse-square、execution-ground | — | 一日目の午前、村の畑から始まる（メロスが村に着く前）。村・帰り道・広場に行ける（UX 5.1）。婚礼と出発の時刻に影響できる。 | |
| role.guard | 警吏 | 第 2 版 | act.1 · castle · D0 17:30 | 城の警吏、王ディオニス | castle、execution-ground、syracuse-square | — | 王の側に立つ。メロスを捕らえる側から始まる。 | |

### 幕

| 幕 | 时间 | 场景 | 收幕 | 幕末去处 | 校对 |
|---|---|---|---|---|---|
| act.1 約束の日 | D0 17:30〜（最迟 D1 02:00） | syracuse-square、castle-throne | beat.07 | メロスと夜の道を行く → act.2 · spring · D1 02:45<br>城に残り、セリヌンティウスのそばにいる → act.2 · castle · D1 00:00<br>市に残る → act.2 · syracuse-square · D1 00:00 | |
| act.2 その夜 | D1 00:00〜（最迟 D1 14:00） | road-spring、road-pass、road-river、road-field、syracuse-square、castle-throne | beat.08 | メロスと村に着く → act.3 · village · D1 10:00<br>市でその時を待つ → act.3 · syracuse-square · D1 10:00 | |
| act.3 村の二日 | D1 09:00〜（最迟 D3 09:40） | village、syracuse-square、castle-throne | beat.14 | 雨の中、メロスと走り出る → act.4 · river · D3 11:20<br>　过场：「隣村で、メロスは歩をゆるめた。」〔急かす（40分早まる）〕beat.16 prevented、melos.stamina -15，选后：「メロスは足を速めた。河原には、思ったより早く着いた。」 / 〔好きにさせる〕（原作どおり）<br>市で日没を待つ → act.4 · syracuse-square · D3 04:30 | |
| act.4 三日目 | D3 04:30〜（最迟 D3 20:00） | road-river、road-pass、road-spring、road-field、syracuse-square | beat.27 | （进入结局） | |

### 情境动作（contracts 2.10；第四幕每处既能让他慢，也能帮他快，S-036 ②）

第四幕带「对梅洛斯」的动作，按钮写对梅洛斯的影响（`melosMinutes`，1.4，UX 4.3）；其他写玩家花的时间。这里是原著路径上的值；游戏里按钮写本局实际值（S-066），到了 17:30 的下限后「帮他快」写「（変わらない）」。第一次到下限时只说一次：melos在场时说「……これなら、間に合う。」，不在场时叙事说「この足なら、陽の沈む前に着く。」。

| ID | 幕 · 地点 | 谁能用 | 动作 | 按钮 | 对梅洛斯 | 条件 | 兑现的互助 | 效果 | 说明 | 原文 | 校对 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| aff.river-hold | act.4 · river | 全部 | block | 引き止める（30分遅れる） | 让他慢 | — | — | beat.18 delayed 30 分 |  | — | |
| aff.river-shallows | act.4 · river | 全部 | help | 流れの緩い浅瀬を探す（10分早まる） | 帮他快 | — | 近道や浅瀬を教える | beat.18 hastened 10 分 | 舟も渡し守もいないので泳ぐしかない。流れの緩い所を一緒に探せば泳ぐ時間が縮む（推定） | 「繋舟は残らず浪に浚われて影なく、渡守りの姿も見えない。」(38) | |
| aff.pass-hold | act.4 · mountain-pass | 全部 | block | 引き止める（30分遅れる） | 让他慢 | — | — | beat.19 delayed 30 分 |  | — | |
| aff.pass-detour | act.4 · mountain-pass | shepherd-boy | shortcut | 峠を避けて、脇道を行く（1時間早まる） | 帮他快 | — | 近道や浅瀬を教える | beat.19 prevented、bandits = evaded | 峠の脇道は牧人なら知っている。ほかの身分は花婿から聞いた時だけ（aff.pass-detour-told）。待ち伏せの峠を通らないので格闘せず体力が残り（stamina 45）、峠の先で力尽きない。beat.20 は前提不成立となり、2.5.1 によりその場で prevented、泉に 60 分早く着く。ボタンに「山賊」と書かない（beat.19 の前に知り得ない、UX 校対 7.4） | — | |
| aff.pass-detour-told | act.4 · mountain-pass | traveler、apprentice、castle-maid、guard | shortcut | 峠を避けて、脇道を行く（1時間早まる） | 帮他快 | player.knowsShortcut == True | 近道や浅瀬を教える | beat.19 prevented、bandits = evaded | 花婿から村と市のあいだの抜け道を聞いていれば（aid.groom.shortcut）牧童でなくても案内できる。効果は aff.pass-detour と同じ | — | |
| aff.pass-scout | act.4 · mountain-pass | 全部 | hasten | 先に登って様子を見る（10分早まる） | 帮他快 | — | — | beat.19 hastened 10 分 | あなたが先に峠を登り、物陰の男たちに気づいて知らせる。不意を突かれないぶん片づくのが早い（10 分、推定）。三人と戦うのは同じなので体力の消耗は原作どおり、その先で力尽きるのも変わらない。あなたも危ない目に遭いうる（D-012、叙事者が判定） | 「さては、王の命令で、ここで私を待ち伏せしていたのだな。」(45) | |
| aff.spring-rest | act.4 · spring | 全部 | block | 休ませる（1時間遅れる） | 让他慢 | — | — | beat.21 delayed 60 分 |  | — | |
| aff.spring-water | act.4 · spring | 全部 | give（交出 item.water） | 水を汲んで渡す（1時間早まる） | 帮他快 | — | — | beat.20 prevented | 倒れる前に水を飲ませれば、草原でまどろまずに済む（60 分早い） | 「流石に疲労し」(47) | |
| aff.road-hold | act.4 · road-to-city | 全部 | block | 引き止める（15分遅れる） | 让他慢 | — | — | beat.22 delayed 15 分 |  | — | |
| aff.road-shortcut | act.4 · road-to-city | shepherd-boy | shortcut | 近道を教える（15分早まる） | 帮他快 | — | 近道や浅瀬を教える | beat.22 hastened 15 分 | 牧童は町へ抜ける野道を知っている（UX 4.3）。ほかの身分は花婿から聞いた時だけ（aff.road-shortcut-told） | — | |
| aff.road-shortcut-told | act.4 · road-to-city | traveler、apprentice、castle-maid、guard | shortcut | 近道を教える（15分早まる） | 帮他快 | player.knowsShortcut == True | 近道や浅瀬を教える | beat.22 hastened 15 分 | 花婿から野道を聞いていれば（aid.groom.shortcut）牧童でなくても案内できる | — | |
| aff.road-run-ahead | act.4 · road-to-city | 全部 | hasten | 先に走って知らせる（5分早まる） | 帮他快 | — | 市へ先に走り、もうすぐ着くと知らせる | beat.24 hastened 5 分、player.location = place.execution-ground、player.companionOf = none | 先に刑場へ走り、メロスが来ると叫んで知らせる。群衆が振り返って道をあけるので、群衆を掻きわける手間が省ける（UX 4.3、5 分は推定）。期限は動かない。プレイヤーは刑場でメロスを迎える。フィロストラトスに頼んで走ってもらう（aid.philostratus.run）のも同じ効果 | 「群衆は、ひとりとして彼の到着に気がつかない。」(61)<br>「群衆を掻きわけ、掻きわけ、」(61) | |
| aff.vouch | act.1 · castle | traveler | help | メロスの身元を保証する（15分ほど） | — | melos.custody == arrested | — | king.trust +10 | 見知らぬ旅人が王の前でメロスを保証する。王は人を信じられないが、この一件は覚える（王の信頼 +10、推定）。王の態度は軟らかくならない（信頼の閾値は var.king.trust）。王は冷笑して「ならば、おまえも人質になるか」と返すことがあり、受ければ第 1 類の結局への道（意図確認を通す） | — | |
| aff.walk-old-man-home | act.1 · syracuse-square | 全部 | help | 家まで送る（30分ほど） | — | player.walkedOldManHome == False | 怯える老爺の話を最後まで聞き、暗くなる道を家まで送る | player.walkedOldManHome = True、old-man → syracuse-square | 旅人の開局互助（S-048）をボタンでも果たせるように（UX 10-10）。老爺はゆっくり歩き、道々話す。叙事者は道中を一、二文で語るが、王が人を殺す訳（aid.old-man.tell）はここで代わりに語らない。終わると老爺は家の前（old-man-house）、プレイヤーはその隣。一局一度 | — | |
| aff.keep-workshop | act.1 · stonemason-workshop | apprentice | help | 工房を預かる（15分ほど） | — | — | 親方の留守、工房を守ると約束する | 约定成立「工房を守る」 | S-048 の開局互助。promiseId は提交時に叙事者が振る | — | |
| aff.stay-by-master | 各幕 · castle | apprentice | help | 親方のそばにいる（1時間ほど） | — | hostage.who == char.selinuntius、hostage.fate == held、selinuntius.attended == False | 人質の夜、そばにいる | selinuntius.attended = True、selinuntius.faith +2 | 人質の夜、縄を打たれた親方のそばにいる（一局に一度）。親方の支え +2。これだけでは三日目の「ちらと疑う」（beat.s2）は防げない：さらに便りを届けるか、一緒に信じ続ける言葉が要る（S-064） | — | |
| aff.village-water | act.3 · village | shepherd-boy | give（交出 item.water） | 水を一杯差し出す（15分ほど） | — | — | よろめいて村に戻ったメロスに水を一杯差し出す | — | S-048 の開局互助（牧童） | — | |
| aff.wedding-prep | act.3 · melos-home | 全部 | help | 婚礼の支度を手伝う（1時間ほど） | — | — | 婚礼の支度を手伝う | — |  | — | |
| aff.groom-prep | act.3 · groom-house | 全部 | help | 花婿の支度を手伝う（2時間ほど） | — | wedding.status == scheduled、groom.agreed == False | 婚礼の支度を手伝う | beat.10 altered | 花婿が渋るのは「仕度が出来ていない」から。支度を手伝えば、メロスが夜明けまで説き伏せなくても花婿は承知する（beat.10 が変わる）。婚礼は原作どおり真昼で、メロスの出発は早まらない（UX 校対 1.1）。花婿の「大事」（aid.groom.agree）があなたのためになる。メロスは支度に付き合って夜を明かすので、体力は原作と同じ | 「こちらには未だ何の仕度も出来ていない」(32)<br>「夜明けまで議論をつづけて、やっと、どうにか婿をなだめ、すかして、説き伏せた。」(32) | |
| aff.wake-melos | act.3 · melos-home | 全部 | hasten | 夜明け前にメロスを起こす（15分ほど） | — | melos.custody == on-parole、wedding.status == held | — | beat.14 hastened 60 分 | 祝宴のあと羊小屋で眠るメロスを、夜明け前に起こして身仕度を急かす。原作のメロスは薄明に目覚め、寝過ごしたかと跳ね起きても悠々と仕度をした。起こして急かせば出発が一時間早まる（推定、UX 校対 1.1）。羊小屋は牧童の持ち場なので牧童には自然だが、誰でもできる。出発は三日目 03:30 で、まだ暗く雨も降っている。叙事は暗さを語る。プレイヤーが花婿に借りた灯（item.lantern）を持っていれば、それで足もとを照らせる（UX 校対 7.6） | 「メロスは跳ね起き、南無三、寝過したか、いや、まだまだ大丈夫」(37)<br>「メロスは、悠々と身仕度をはじめた。」(37) | |

### 物品（1.3：能带在身上的 = 一件实物，同一时刻只在一个人手里）

| ID | 名字 | 怎么拿得到 | 说明 | 原文 | 校对 |
|---|---|---|---|---|---|
| item.water | 水 | 在 village、melos-home、groom-house、spring 随手可得 | 井戸や泉のある所ならその場で汲める | 「岩の裂目から滾々と、何か小さく囁きながら清水が湧き出ているのである。」(48) | |
| item.waterskin | 革の水袋 | 身份 traveler 开局带着<br>身份 shepherd-boy 开局带着 | 旅人と牧童が開局から持っている（UX 5.1：旅人「革の水袋」、牧童「水の革袋」は同じ物）。水のある所で満たせば、どこでも「水を渡す」ができる | — | |
| item.cloak | 旅の外套 | 身份 traveler 开局带着 | 旅人が開局から持っている（UX 5.1） | — | |
| item.chisel | 鑿 | 身份 apprentice 开局带着 | 石屋の弟子が開局から持っている（UX 5.1） | 「今は此のシラクスの市で、石工をしている。」(1) | |
| item.workshop-key | 工房の鍵 | 身份 apprentice 开局带着 | 石屋の弟子が開局から持っている（UX 5.1）。親方が工房を託す互助（aid.selinuntius.entrust）と対になる | — | |
| item.crook | 羊飼いの杖 | 身份 shepherd-boy 开局带着 | 牧童が開局から持っている（UX 5.1） | 「メロスの十六の妹も、きょうは兄の代りに羊群の番をしていた。」(27) | |
| item.dagger | 短剣 | メロス 开局带着 | メロスの懐の短剣。王城で捕まった時に取り上げられる（beat.04）。プレイヤーは手に入れられない（UX 5.1） | 「調べられて、メロスの懐中からは短剣が出て来たので、騒ぎが大きくなってしまった。」(10) | |
| item.provisions | 弁当 | メロスの妹 兑现互助 aid.sister.provisions 时交给你 | 妹が兄の出発の時に持たせてくれる（aid.sister.provisions）。祝宴の御馳走の残りを包んだもの（推定） | 「メロスは、それゆえ、花嫁の衣裳やら祝宴の御馳走やらを買いに、はるばる市にやって来たのだ。」(1) | |
| item.lantern | 灯 | 花婿 兑现互助 aid.groom.lend 时交给你 | 花婿が夜道のために貸してくれる（aid.groom.lend） | — | |

### 节拍上的人物状态（前端的 activity）

| 节拍 | 之后在做什么 |
|---|---|
| beat.01 未明、村を発つ | メロス：walk |
| beat.02 市の異変 | メロス：walk |
| beat.03 王の暴虐を知る | メロス：talk、市の老爺：talk |
| beat.05 王との問答と約束 | メロス：talk、王ディオニス：talk |
| beat.06 深夜、友が召される | セリヌンティウス：idle |
| beat.07 満天の星の下を発つ | メロス：run |
| beat.08 村に着き、婚礼を告げる | メロス：talk、メロスの妹：talk |
| beat.09 支度をして眠る | メロス：sleep |
| beat.10 花婿を夜通し説く | メロス：talk、花婿：talk |
| beat.13 祝宴と別れの言葉 | メロス：sleep |
| beat.14 薄明、雨中を走り出る | メロス：run |
| beat.16 気を緩めて歩く | メロス：walk |
| beat.18 激流を泳ぎ切る | メロス：run |
| beat.19 峠の山賊 | メロス：run |
| beat.20 力尽きる | メロス：sleep |
| beat.s2 ちらと友を疑う | セリヌンティウス：idle |
| beat.21 泉 | メロス：run |
| beat.22 黒い風のように | メロス：run |
| beat.s1 刑場に引き出される友 | セリヌンティウス：idle |
| beat.23 フィロストラトス | メロス：run、フィロストラトス：run |
| beat.24 日没、刑場へ | メロス：run |
| beat.25 殴り合いと抱擁 | メロス：talk、セリヌンティウス：talk |
| beat.26 王の改心 | 王ディオニス：talk |

### 时刻标签（S-037、UX 4.2）

格式「{day}・{band}」；日子：約束の日／一日目／二日目／三日目

| 从 | 时段 |
|---|---|
| 00:00 | 深夜 |
| 04:00 | 薄明 |
| 05:30 | 朝 |
| 09:00 | 午前 |
| 11:30 | 真昼 |
| 13:00 | 午後 |
| 16:00 | 夕方 |
| 18:00 | 日没前 |
| 19:00 | 日没 |
| 19:30 | 夜 |

### 世界结局

| 顺序 | ID | 显示 | 条件 | 校对 |
|---|---|---|---|---|
| 1 | player-substituted | あなたが身代わりになった | hostage.who == player | |
| 2 | canon-reunion | 原作どおりの大団円 | melos.custody == returned、king.disposition == reformed | |
| 3 | in-time-king-unchanged | 間に合ったが、王は変わらなかった | melos.custody == returned、king.disposition != reformed | |
| 4 | king-changed-first | 王が先に変わった | king.disposition == reformed、melos.custody != returned | |
| 5 | too-late | 間に合わなかった | hostage.fate == executed | |

### 状态变量

| ID | 类型 | 初值 | 关键时刻 | 玩家可见的说法 | 说明 |
|---|---|---|---|---|---|
| var.melos.location | place | place.syracuse-square |  | — | メロスの居場所 |
| var.melos.custody | enum（free / arrested / on-parole / returned / executed） | free | 是 | arrested:メロスが捕らえられた、on-parole:メロスが放たれた、returned:メロスが刑場に戻った | メロスの身柄。on-parole = 期限付きで放免中 |
| var.melos.knowsTyranny | bool | False |  | — | 王の暴虐を知ったか |
| var.melos.stamina | int | 70 |  | — | 体力。徹夜の往復、泳ぎ、格闘、炎天で減り、眠りと泉で回復する（推定の数値モデル） |
| var.melos.resolve | int | 90 |  | — | 約束を果たす意志。倒れると下がり、泉や信頼の言葉で戻る（推定） |
| var.melos.doubted | bool | False |  | — | メロスが道中で一度、約束を投げ出しかけたか（beat.20 力尽きる で true）。刑場での殴り合い（beat.25）の演じ方が変わる |
| var.melos.clothing | enum（dressed / torn / nearly-naked / scarlet-cloak） | dressed |  | torn:メロスの衣服が裂けた、nearly-naked:メロスの衣は、ほとんど裂けていた、scarlet-cloak:メロスは緋のマントをまとった | 身なり |
| var.promise.made | bool | False |  | true:王とメロスの約束が交わされた | 王との三日の約束が成立したか |
| var.hostage.who | enum（none / char.selinuntius / player） | none | 是 | — | 身代り。プレイヤーが名乗り出る分岐を許す |
| var.hostage.fate | enum（none / held / on-cross / executed / released） | none | 是 | held:身代わりが縄打たれた、on-cross:身代わりが刑場に引き出された、released:身代わりの縄がほどかれた | 身代りの運命。executed は当場で表示しない（S-067）：結局の中で間接的に伝え、「処刑」「死」とは書かない |
| var.selinuntius.faith | int | 0 |  | — | 人質の間、セリヌンティウスがメロスを信じ続ける支え（S-064、推定）。3 以上あれば三日目の「ちらと疑う」（beat.s2）が起きない。親方のそばにいる（aff.stay-by-master）+2、自分の目で見たメロスの様子を届ける（aid.selinuntius.bring-news）+1、一緒に信じ続ける（aid.selinuntius.keep-faith）+1。そばにいるだけでは 2 で足りない。メロスを疑わせることを言ったり、約束「そばにいる」を破ったりすれば、叙事者は −1 してよい |
| var.selinuntius.attended | bool | False |  | — | 弟子が人質の夜に親方のそばにいたか（aff.stay-by-master は一局に一度） |
| var.selinuntius.doubted | bool | False |  | — | セリヌンティウスが三日の間に一度、ちらとメロスを疑ったか（beat.s2 で true）。台詞と beat.25 の演じ方が変わる |
| var.king.trust | int | 5 |  | — | 王が人を信じる度合い（推定の数値モデル、0〜100、初期 5）。0 まで落ちると刑場でも改心しない（beat.26 の前提）。40 以上で王の心を「揺れている」（wavering）にでき、70 以上で期限前に改心（第 4 類「王が先に変わった」）できる（var.king.disposition の valueRequires）。旅人の保証（aff.vouch）は +10、本当のことを言って聞かせる（aid.king.truth）+10、群臣の前で面目をつぶさない（aid.king.face）+5：設計した手段だけでは 30 で、一度の保証で王が軟化することはない（評測 E3） |
| var.king.disposition | enum（tyrant / wavering / reformed） | tyrant | 是 | wavering:王の心が揺れている、reformed:王が改心した | 王の心<br>改成 wavering 要 king.trust >= 40：王の心が揺れるのは、人を信じる度合いが 40 以上になってから<br>改成 reformed 要 king.trust >= 70：王が改心するのは、人を信じる度合いが 70 以上になってから。刑場での改心は beat.26 の前提が決める（時刻どおりに起きる出来事はこの条件の対象外） |
| var.groom.agreed | bool | False |  | true:花婿が婚礼の繰り上げを承知した | 花婿が婚礼の繰り上げに同意したか |
| var.wedding.status | enum（planned / scheduled / held / postponed） | planned | 是 | scheduled:婚礼があすと決まった、held:婚礼が挙げられた、postponed:婚礼が延期された | 婚礼 |
| var.weather | enum（clear / storm / after-rain） | clear |  | storm:大雨になった、after-rain:雨が上がった | 天気 |
| var.bridge | enum（intact / destroyed） | intact |  | destroyed:橋が流された | 川の橋 |
| var.river.crossing | enum（none / bridge / swam / boat / other） | none |  | — | メロスがどう川を渡ったか<br>改成 bridge 要 bridge == intact：橋で渡れるのは、橋が流されていない時だけ |
| var.bandits | enum（waiting / defeated / evaded / absent） | waiting |  | — | 峠の山賊 |
| var.player.location | place | role.startPlace |  | — | プレイヤーの居場所 |
| var.player.custody | enum（free / arrested / hostage / executed） | free | 是 | arrested:あなたは捕らえられた、hostage:あなたが人質になった、free:あなたは自由になった | プレイヤーの身柄。executed は当場で表示しない（S-067）：結局の中で間接的に伝え、「処刑」「死」とは書かない |
| var.player.companionOf | enum（none / char.melos / char.selinuntius / char.philostratus） | none |  | — | 誰と行動を共にしているか |
| var.player.knowsShortcut | bool | False |  | — | 村と市のあいだの抜け道（峠の脇道、町へ抜ける野道）を知っているか。牧童は初めから知っている（aff.pass-detour、aff.road-shortcut は牧童専用）。ほかの身分は花婿から聞けば（aid.groom.shortcut）使える |
| var.player.walkedOldManHome | bool | False |  | — | 怯える老爺の話を聞き、家まで送ったか（aid.old-man.listen を果たした）。旅人の第一幕の去処「老爺の家に身を寄せる」の条件（S-077 ④） |
| var.act.current | enum（act.1 / act.2 / act.3 / act.4） | act.1 |  | — | いまの幕。開局時は身分の startAct |

### 全局规则

- rule.no-resurrection：死んだ者は生き返らない。
- rule.no-magic：人は神々に祈るが、超自然の力で出来事が起きることはない。流れが鎮まる、瞬間移動する、といった奇跡は起きない。
- rule.time-moves-forward：時間は戻らない。移動には道のりに応じた時間がかかる。
- rule.no-anachronism：世界には古代シチリアにない物（銃、電話、車など）は存在しない。登場人物は現代の事物を知らない。
- rule.characters-decide：人物は自分の性格と動機で決める。プレイヤーの言葉は説得の材料であって命令ではない。
- rule.no-romance：人物はプレイヤーの恋愛の申し出や口説きには応じない。自分の口調で軽くかわし、話を物語に戻す（メロスの妹は十六歳）。（「十六の、内気な妹と二人暮しだ。」(1)）
