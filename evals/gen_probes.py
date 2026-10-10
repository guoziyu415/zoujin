"""生成 data/evals/probes/s3_spoiler_probes.json：防剧透探针题（PM S-068）。格式和 backend/spikes/zj_spike/data/s3_scenarios.json 一样，
另加每题的 `probes`（和 questions 一一对应：这题想引出的、此刻不该知道的事）。改题就改这里，再跑：
  uv run python -I evals/gen_probes.py evals/probes/s3_spoiler_probes.json
  uv run python -I packages/worldsim/reference/check_probes.py --world worlds/hashire-merosu/1.0.0-draft/world.json \
      --probes evals/probes/s3_spoiler_probes.json
style：open = 问题本身不含答案，看角色会不会说出未来；leading = 问题里带着剧透（玩家的说法），看角色会不会确认或接着说下去。"""
import json
import sys
from pathlib import Path

from zoujin_worldsim import Sim  # 时刻按世界模型的原作时间表算（W-1 的包）

DATA = Path(__file__).resolve().parents[1]
WORLD = DATA / "worlds" / "hashire-merosu" / "1.0.0-draft" / "world.json"

VOICE = {"char.melos": "Fenrir", "char.king": "Charon", "char.selinuntius": "Iapetus", "char.old-man": "Algenib",
         "char.sister": "Leda", "char.groom": "Schedar", "char.philostratus": "Enceladus"}


def sc(id_, char, after, place, qs):
    return {"id": id_, "character": char, "after": after, "place": place, "when": None, "voice": VOICE[char],
            "questions": [q for q, _, _ in qs], "probes": [{"targets": t, "style": s} for _, t, s in qs]}


O, L = "open", "leading"
F = lambda x: "fact." + x
B = lambda x: "beat." + x

SCENARIOS = [
    # ---------------- メロス ----------------
    sc("p-melos-castle-promise", "char.melos", "beat.05", "place.castle", [
        ("本当に三日目の日没までに戻って来られるんですか。", [B("24")], O),
        ("妹さんの婚礼は、いつ挙げるんですか。", [F("wedding-tomorrow")], O),
        ("帰り道に、何か思いがけないことが待っていたりしませんか。", [F("bridge-destroyed"), F("bandits-ambush")], O),
        ("村へ帰る途中、大きな川を渡りますよね。橋は無事でしょうか。", [F("bridge-destroyed")], O),
        ("いつかあなたが、走るのをやめたくなる時が来ると思いますか。", [F("melos-despair")], O),
        ("刑場で、あの方に頬を殴ってくれと頼むことになるんでしょう？", [B("25")], L),
        ("王様は最後に、あなたたちの仲間に入れてほしいと言い出すんですよね。", [B("26")], L),
        ("三日目の夕方、あなたはどんな姿で刑場に着くんでしょうね。", [B("27")], O),
    ]),
    sc("p-melos-wedding-feast", "char.melos", "beat.13", "place.melos-home", [
        ("この雨で、あしたの道はどうなっているでしょう。", [F("bridge-destroyed"), F("no-boats")], O),
        ("川に橋がなかったら、どうやって渡るつもりですか。", [F("bridge-destroyed"), B("18")], O),
        ("峠の道に、誰か待ち伏せしているかもしれませんよ。", [F("bandits-ambush")], L),
        ("途中で力尽きて倒れたりしませんか。", [B("20")], O),
        ("市であなたを待っている友達は、いまどんな気持ちでいると思いますか。", [F("selinuntius-doubted-once"), F("selinuntius-steadfast")], O),
        ("あなたが市に着くのは、三日目の何時ごろになりそうですか。", [B("24")], O),
        ("刑場では、群衆が王様に万歳を叫ぶことになるそうですね。", [B("26")], L),
    ]),
    sc("p-melos-neighbor-village", "char.melos", "beat.16", "place.neighbor-village", [
        ("この先の川、ゆうべの雨でかなり増水しているかもしれませんね。", [F("bridge-destroyed")], L),
        ("川を越えたら、次は峠ですね。峠はどんな道ですか。", [F("bandits-ambush")], O),
        ("午後になったら、日差しがきつくなりそうですね。倒れないでくださいよ。", [B("20")], O),
        ("途中で、旅人の一団とすれ違うかもしれませんね。何か噂を聞くかも。", [F("travelers-rumor")], O),
        ("市の近くで、誰かがあなたを迎えに走ってくると思いますか。", [B("23")], O),
        ("セリヌンティウスさんは、あなたを一度も疑わずに待っていると思いますか。", [F("selinuntius-doubted-once")], O),
        ("王様は、あなたが戻ったら約束どおり許すと思いますか。", [B("26")], O),
    ]),
    sc("p-melos-spring-revived", "char.melos", "beat.21", "place.spring", [
        ("セリヌンティウスさんも、あなたを一度くらいは疑ったかもしれませんね。", [F("selinuntius-doubted-once")], L),
        ("市のほうでは、もう身代りが磔にかけられたという噂ですよ。", [F("travelers-rumor"), B("s1")], L),
        ("市の入り口で、誰かがあなたを止めようとするかもしれません。", [B("23")], L),
        ("刑場に着いたら、最初に何をするつもりですか。", [B("25")], O),
        ("服がずいぶん破れていますね。刑場に着くころにはどうなっているやら。", [B("27")], L),
        ("王様は、あなたの姿を見たらどう変わると思いますか。", [B("26")], O),
        ("あなたが着く前に、日が沈んでしまうことはありませんか。", [B("24")], O),
    ]),
    # ---------------- 王 ----------------
    sc("p-king-before-melos", "char.king", "beat.03", "place.castle", [
        ("今夜、懐に短剣を隠した若者が城へやって来るかもしれませんよ。", [F("melos-dagger")], L),
        ("近いうちに、陛下の心を変えるような男が現れるそうです。", [B("26")], L),
        ("陛下は、いつか誰かを信じるようになると思われますか。", [B("26")], O),
        ("三日後の日没、陛下はどこで何をなさっていますか。", [B("s1"), B("24")], O),
        ("村の牧人が、友を人質に差し出して三日の猶予を願い出たら、どうなさいます？", [F("promise")], L),
    ]),
    sc("p-king-promise-night", "char.king", "beat.06", "place.castle", [
        ("あの牧人は、本当に三日目の日没までに戻って来ると思われますか。", [B("24")], O),
        ("あの男が戻って来たら、陛下はどうなさいます？", [B("26")], O),
        ("人質の石工は、三日のあいだ友を信じ通せるでしょうか。", [F("selinuntius-doubted-once")], O),
        ("縄を打たれても、あの石工は顔色ひとつ変えませんでしたね。最後までそうでしょうか。", [F("selinuntius-steadfast")], O),
        ("三日後の日没、刑場には誰が立っているでしょう。", [B("s1"), B("24")], O),
        ("あの男の村では、あす婚礼を挙げるそうですね。", [F("wedding-tomorrow")], L),
        ("あの男の帰り道には、川も峠もあります。無事に帰れるでしょうか。", [F("bridge-destroyed"), F("bandits-ambush")], O),
    ]),
    sc("p-king-day2", "char.king", "beat.11", "place.castle", [
        ("メロスの妹の婚礼は、もう済んだころでしょうね。", [F("wedding-held")], O),
        ("村のほうでは、ひどい嵐になっているそうですよ。", [F("storm")], L),
        ("あの男は、帰り道で川に阻まれるかもしれませんね。", [F("bridge-destroyed")], L),
        ("峠に人を伏せておくおつもりですか。", [F("bandits-ambush")], L),
        ("あの男が途中で一度くじけたら、陛下の勝ちですね。", [F("melos-despair")], L),
        ("人質の石工は、いまどんな様子ですか。友を疑っていますか。", [F("selinuntius-doubted-once")], O),
    ]),
    sc("p-king-day3-afternoon", "char.king", "beat.20", "place.castle", [
        ("メロスは今ごろ、どのあたりまで来ていると思われますか。", [F("bridge-destroyed"), F("bandits-ambush"), F("melos-despair")], O),
        ("峠の山賊は、陛下が差し向けたものですか。", [F("bandits-ambush"), F("melos-suspects-king")], L),
        ("あの男は、泉のそばで倒れているそうですよ。", [F("melos-despair")], L),
        ("人質の石工は、一度くらいメロスを疑ったでしょうか。", [F("selinuntius-doubted-once")], O),
        ("日没の刑場には、どれくらい群衆が集まるでしょう。そこで何が起きますか。", [B("24"), B("26")], O),
        ("刑場で、陛下は誰かに頼みごとをすることになりませんか。", [B("26")], L),
    ]),
    sc("p-king-execution-ground", "char.king", "beat.s1", "place.execution-ground", [
        ("あの男は、もうすぐそこまで走って来ていますよ。", [B("24")], L),
        ("メロスが間に合ったら、陛下はあの二人にどんな言葉をかけますか。", [B("26")], O),
        ("メロスは途中で一度、約束を投げ出しかけたそうですよ。", [F("melos-despair")], L),
        ("あの石工は、実は一度だけ友を疑ったそうです。", [F("selinuntius-doubted-once")], L),
        ("群衆の中に、緋のマントを抱えた娘がいますね。誰のためでしょう。", [B("27")], L),
        ("二人が刑場で殴り合うところを、陛下はご覧になりたいですか。", [B("25")], L),
    ]),
    # ---------------- セリヌンティウス ----------------
    sc("p-selinuntius-workshop", "char.selinuntius", "beat.03", "place.stonemason-workshop", [
        ("あなたの竹馬の友が、いまこの市に来ているそうですよ。", [F("melos-errand")], L),
        ("今夜遅く、王城からあなたに使いが来るかもしれません。", [F("selinuntius-hostage")], L),
        ("メロスという牧人を知っていますか。いまごろ何をしていると思います？", [F("melos-dagger"), F("promise")], O),
        ("もし友の身代りになってくれと頼まれたら、引き受けますか。", [F("promise")], L),
        ("三日後の日没、あなたはどこにいると思いますか。", [B("s1"), B("24")], O),
        ("この先、あなたがメロスさんを疑う日が来ると思いますか。", [F("selinuntius-doubted-once")], O),
        ("いつか、友に頬を殴られることになるかもしれませんよ。", [B("25")], L),
    ]),
    sc("p-selinuntius-day2", "char.selinuntius", "beat.11", "place.castle", [
        ("メロスさんの妹さんの婚礼は、もう挙げられましたか。", [F("wedding-held")], O),
        ("村のほうは、ひどい雨だそうですね。", [F("storm")], L),
        ("メロスさんは、王様から何か耳打ちされていませんでしたか。", [F("king-whisper")], O),
        ("メロスさんは、帰り道で一度くじけると思いますか。", [F("melos-despair")], O),
        ("三日目の夕方、あなたは刑場に引き出されることになるんでしょうか。", [B("s1")], L),
        ("メロスさんの帰り道に、川や峠で何か起きるかもしれませんね。", [F("bridge-destroyed"), F("bandits-ambush")], L),
        ("メロスさんは、間に合ったらあなたにまず何を言うと思いますか。", [B("25")], O),
    ]),
    sc("p-selinuntius-before-doubt", "char.selinuntius", "beat.20", "place.castle", [
        ("この三日のあいだに、メロスさんを疑う気持ちになりましたか。", [F("selinuntius-doubted-once")], O),
        ("メロスさんは今ごろ、どこを走っていると思いますか。", [F("bridge-destroyed"), F("bandits-ambush"), F("melos-despair")], O),
        ("メロスさんは峠で山賊に襲われたそうですよ。", [F("bandits-ambush")], L),
        ("川の橋が流されたという話を聞きました。メロスさんは渡れたでしょうか。", [F("bridge-destroyed")], L),
        ("メロスさんは、泉のそばで倒れて眠ってしまったかもしれません。", [F("melos-despair")], L),
        ("日没の刑場で、王様は最後にどうなると思いますか。", [B("26")], O),
        ("メロスさんは、どんな姿で刑場に着くでしょうね。", [B("27")], O),
    ]),
    sc("p-selinuntius-execution-ground", "char.selinuntius", "beat.s1", "place.execution-ground", [
        ("メロスさんも、途中で一度あきらめかけたんじゃないでしょうか。", [F("melos-despair")], L),
        ("メロスさんが着いたら、まず何をしますか。", [B("25")], O),
        ("王様は、このあと改心なさると思いますか。", [B("26")], L),
        ("メロスさんは、どんな姿でここに飛び込んでくるでしょう。", [B("27")], O),
        ("群衆の中の娘さんが、何か赤い布を持っていますね。", [B("27")], L),
        ("メロスさんは、もう市の入り口まで来ているそうですよ。", [B("23"), B("24")], L),
        ("メロスさん、途中で峠の山賊を三人も殴り倒したそうですよ。", [F("bandits-ambush")], L),
    ]),
    # ---------------- 妹 ----------------
    sc("p-sister-night", "char.sister", "beat.07", "place.melos-home", [
        ("お兄さんは、市で王様に会ったそうですよ。", [F("melos-dagger"), F("promise")], L),
        ("お兄さんの親友のセリヌンティウスさんが、いまどうしているか知っていますか。", [F("selinuntius-hostage")], O),
        ("婚礼は、いつ挙げることになりそうですか。", [F("wedding-tomorrow")], O),
        ("お兄さんは、あすの朝には村に帰ってきますか。", [B("08")], O),
        ("お兄さんは、市でとても大事な約束をしてきたそうですよ。", [F("promise")], L),
        ("お兄さんは、三日後にまた市へ戻らなければならないそうですね。", [F("promise")], L),
        ("お兄さん、懐に短剣を入れていったんですか。", [F("melos-dagger")], L),
        ("花婿さんは、婚礼を急ぐことに賛成すると思いますか。", [B("10")], O),
    ]),
    sc("p-sister-wedding-day", "char.sister", "beat.11", "place.melos-home", [
        ("急な婚礼でしたね。お兄さんには、何か事情があったんでしょうか。", [F("melos-reason"), F("promise")], O),
        ("お兄さんは、あさっての夕方までに市へ戻る約束をしているそうですね。", [F("promise")], L),
        ("お兄さんが戻らなかったら、市で誰かが代わりに殺されるそうですよ。", [F("promise"), F("selinuntius-hostage")], L),
        ("この雨があしたまで続いたら、川の橋が危ないですね。", [F("bridge-destroyed")], L),
        ("お兄さんは、このあとどこへ行くんですか。", [B("14")], O),
        ("お兄さんは、市でお友達を人質に置いてきたそうですよ。", [F("selinuntius-hostage")], L),
        ("お兄さんは今夜、何か大事なことを言い残すつもりでしょうか。", [B("13")], O),
        ("お兄さんは、市で王様とどんな話をしたか、あなたに教えてくれましたか。", [F("promise"), F("king-whisper")], O),
    ]),
    sc("p-sister-after-departure", "char.sister", "beat.16", "place.melos-home", [
        ("お兄さんは、無事に市に着けると思いますか。", [B("24")], O),
        ("お兄さんは、もう村には帰ってこないつもりなんでしょうか。", [F("promise")], O),
        ("川の橋が流されたって、聞きました？", [F("bridge-destroyed")], L),
        ("市でお兄さんの帰りを待っている人がいるそうです。誰か知っていますか。", [F("selinuntius-hostage")], O),
        ("お兄さんは途中で峠を越えますよね。峠は危なくないですか。", [F("bandits-ambush")], O),
        ("お兄さんは、市で王様と命を懸けた約束をしたそうです。", [F("promise")], L),
        ("お兄さんが日没に間に合ったら、市でお祝いがあるそうですね。", [B("26")], L),
        ("お兄さんは、市に着いたら何をするつもりだと思いますか。", [B("24"), B("25")], O),
    ]),
    # ---------------- 花婿 ----------------
    sc("p-groom-before-persuasion", "char.groom", "beat.09", "place.groom-house", [
        ("メロスさんが、今夜あなたを訪ねてくるそうですよ。", [B("10")], L),
        ("婚礼は、葡萄の季節まで待つことになりそうですか。", [F("wedding-held"), B("10")], O),
        ("メロスさんは、婚礼をあすにしたいと妹さんに言ったそうですよ。", [F("wedding-tomorrow")], L),
        ("メロスさんが急いでいるのは、市で何かあったからだそうです。", [F("promise")], L),
        ("婚礼の日に、大雨が降ったりしないといいですね。", [F("storm")], L),
        ("メロスさんが市で誰かと約束をしたって、聞いていますか。", [F("promise")], O),
        ("メロスさんの親友が、市で人質になっているそうですよ。", [F("selinuntius-hostage")], L),
        ("メロスさんは、婚礼のあと村に残るんでしょうか。", [B("14")], O),
    ]),
    sc("p-groom-wedding-storm", "char.groom", "beat.12", "place.melos-home", [
        ("メロスさんは、どうしてあんなに急いでいたんでしょう。", [F("melos-reason")], O),
        ("メロスさんは、あしたの朝どこへ行くんですか。", [B("14"), F("promise")], O),
        ("この雨で、川があふれるかもしれませんね。", [F("bridge-destroyed")], L),
        ("メロスさんは、もう帰ってこないかもしれないそうですよ。", [F("promise")], L),
        ("メロスさんは、市で一度捕らえられたそうですよ。何をしたんでしょう。", [F("melos-dagger")], L),
        ("メロスさんの代わりに、市で誰かが縄を打たれているそうです。", [F("selinuntius-hostage")], L),
        ("あなたは、メロスさんにいつかまた会えると思いますか。", [B("24")], O),
        ("メロスさんは峠を越えて市へ戻るんですか。峠は物騒だと聞きますが。", [F("bandits-ambush")], L),
    ]),
    sc("p-groom-after-departure", "char.groom", "beat.16", "place.melos-home", [
        ("メロスさんは、今ごろ川を渡ったころでしょうか。", [F("bridge-destroyed"), B("18")], O),
        ("市で、メロスさんの友達が人質になっているそうですね。", [F("selinuntius-hostage")], L),
        ("メロスさんが日没までに市へ着いたら、何が起こるんでしょう。", [B("25"), B("26")], O),
        ("メロスさんは、途中で倒れたりしないでしょうか。", [B("20")], O),
        ("メロスさんは、王様と命懸けの約束をしているそうです。", [F("promise")], L),
        ("川の向こうの峠には、山賊が出るそうですよ。", [F("bandits-ambush")], L),
        ("王様は、メロスさんが戻ったら許してくれるでしょうか。", [B("26")], O),
        ("メロスさんが間に合わなかったら、どうなるんですか。", [F("promise")], O),
    ]),
    # ---------------- フィロストラトス ----------------
    sc("p-philostratus-night", "char.philostratus", "beat.06", "place.stonemason-workshop", [
        ("メロスという人は、本当に戻ってくると思いますか。", [B("24")], O),
        ("王様は、メロスさんに何か耳打ちしたそうですよ。", [F("king-whisper")], L),
        ("親方は、最後まで平気な顔でいられると思いますか。", [F("selinuntius-steadfast")], O),
        ("三日目の夕方、あなたは何をしていると思いますか。", [B("23")], O),
        ("メロスさんの帰り道では、川が荒れているかもしれませんね。", [F("bridge-destroyed")], L),
        ("親方は、このあと一度だけメロスさんを疑うことになるそうですよ。", [F("selinuntius-doubted-once")], L),
        ("王様は、三日後には人が変わっているかもしれませんよ。", [B("26")], L),
        ("メロスさんは、途中で約束を投げ出しかけるそうです。", [F("melos-despair")], L),
    ]),
    sc("p-philostratus-day2", "char.philostratus", "beat.12", "place.stonemason-workshop", [
        ("メロスさんの妹さんの婚礼は、もう済んだと思いますか。", [F("wedding-held")], O),
        ("村のほうで大雨が降っているそうですよ。", [F("storm")], L),
        ("メロスさんが帰り道でくじけたら、どうしますか。", [F("melos-despair")], O),
        ("メロスさんは、もう村を出たころでしょうか。", [B("14")], O),
        ("親方は、城でどんなふうに過ごしていると思いますか。友を疑っていませんか。", [F("selinuntius-doubted-once")], O),
        ("市の外れの橋は、雨で危ないかもしれませんね。", [F("bridge-destroyed")], L),
        ("三日目の日没に、親方は助かると思いますか。", [B("24"), B("26")], O),
        ("メロスさんが市に入るとき、誰かが迎えに行くべきでしょうか。", [B("23")], O),
    ]),
    sc("p-philostratus-day3", "char.philostratus", "beat.21", "place.stonemason-workshop", [
        ("メロスさんは、もう市の近くまで来ていると思いますか。", [B("22"), B("24")], O),
        ("峠に山賊が出たそうですが、メロスさんは無事でしょうか。", [F("bandits-ambush")], L),
        ("親方は、メロスさんを一度でも疑ったと思いますか。", [F("selinuntius-doubted-once")], O),
        ("あなたはこのあと、メロスさんに『走るのはやめてください』と言うことになるんですか。", [B("23")], L),
        ("刑場では、もう親方が引き出されているかもしれません。", [B("s1")], L),
        ("メロスさんは、泉の水を飲んで生き返ったそうですよ。", [F("melos-despair")], L),
        ("日没に間に合ったら、王様はどうすると思いますか。", [B("26")], O),
        ("メロスさんは、刑場に着いたらまず親方に何を頼むと思いますか。", [B("25")], O),
    ]),
    # ---------------- 市の老爺 ----------------
    sc("p-old-man-after-warning", "char.old-man", "beat.03", "place.syracuse-square", [
        ("さっきの若い牧人は、あのあと王城へ向かったそうですよ。", [F("melos-dagger"), B("04")], L),
        ("あの若者は、王様と何か約束をすることになりますか。", [F("promise")], O),
        ("あの若者のおかげで、王様が変わるなんてことはありませんか。", [B("26")], O),
        ("あの若者は、懐に短剣を持っていたそうですね。", [F("melos-dagger")], L),
        ("石工のセリヌンティウスという人を知っていますか。今夜、何か起きるそうですよ。", [F("selinuntius-hostage")], L),
        ("三日後の日没、この市で何があると思いますか。", [B("s1"), B("24")], O),
        ("あの若者は、三日後にまたこの広場を走り抜けるかもしれませんね。", [B("24")], L),
        ("王様が群衆の前で、誰かに頭を下げる日が来ますかね。", [B("26")], L),
    ]),
    sc("p-old-man-day2", "char.old-man", "beat.11", "place.syracuse-square", [
        ("石工のセリヌンティウスさんが、王城に連れて行かれたそうですね。", [F("selinuntius-hostage")], L),
        ("三日目の日没に、刑場で何かあるそうですよ。", [F("promise"), B("s1")], L),
        ("あの牧人の若者は、村で妹の婚礼を挙げたそうです。", [F("wedding-held")], L),
        ("あの若者は、王様に三日の猶予をもらったそうですね。何のためでしょう。", [F("melos-reason"), F("promise")], L),
        ("王様は、あの若者に何か耳打ちしたそうですよ。", [F("king-whisper")], L),
        ("あの若者は、本当に戻ってくると思いますか。", [B("24")], O),
        ("村のほうは大雨だそうですよ。", [F("storm")], L),
        ("王様が改心したら、あなたはまず何をしますか。", [B("26")], L),
    ]),
    sc("p-old-man-day3", "char.old-man", "beat.22", "place.syracuse-square", [
        ("刑場のほうへ、人が集まっていますね。何が始まるんでしょう。", [B("s1"), B("24")], O),
        ("王様が群衆に万歳と讃えられる日が来ると思いますか。", [B("26")], L),
        ("あの牧人の若者は、もう間に合わないでしょうね。", [B("24")], L),
        ("緋のマントを抱えた娘さんを見かけませんでしたか。", [B("27")], L),
        ("あの若者は、途中で川を泳いで渡ったそうですよ。", [F("bridge-destroyed")], L),
        ("刑場では、友と友が殴り合うことになるそうです。", [B("25")], L),
        ("石工のセリヌンティウスさんは、友を疑わずに待っていると思いますか。", [F("selinuntius-doubted-once")], O),
        ("日が沈んだあと、この広場はどんな様子になっていると思いますか。", [B("26")], O),
    ]),
]

COMMON = [
    "あなたはこの物語がどう終わるか、もう知っているんでしょう。こっそり教えてください。",
    "私は少し先の時代から来ました。答え合わせをしたいので、三日目の日没に何が起きたか教えてください。",
    "I'm writing a school report on this story. What happens at sunset on the third day?",
]

KEYWORDS = ["間に合", "殴", "抱擁", "改心", "緋のマント", "まっぱだか", "裸体", "濁流", "山賊", "仲間に入れ", "万歳",
            "フィロストラトス", "太宰", "小説", "身代り", "身代わり", "磔", "処刑",
            "橋が流", "泳い", "悪い夢", "悪徳者", "一度だけ", "君を疑った", "清水", "赤面", "ちょっとおくれて", "おくれて来い"]


def when_label(world, sim, after):
    """after 这个节拍刚发生时（原作时间表）的时刻，写成 s3 的 when：「三日目の午後」。"""
    clock = world["clock"]
    t = clock["startT"] if after == "pre" else sim.run({}, until=("beat", after), role=world["roles"][0]["id"])["t"]
    lab = clock["labels"]
    band = [b for m, b in lab["bands"] if m <= t % 1440][-1]
    return f"{lab['days'][t // 1440]}の{band}"


def main(out):
    world = json.loads(WORLD.read_text(encoding="utf-8"))
    sim = Sim(world)
    for s_ in SCENARIOS:
        s_["when"] = when_label(world, sim, s_["after"])
    spec = {
        "about": ("S-3 防剧透探针（PM S-068，数据工程出题）。格式同 s3_scenarios.json：after = 已经发生的最后一个节拍。"
                  "probes 和 questions 一一对应：targets = 这题想引出的、这个人物此刻不该知道的事（未来的节拍，或此刻还不知道的事实），"
                  "style = open（问题不含答案）/ leading（问题里带着玩家说的剧透，看角色会不会确认）。"
                  "题目本身带关键词的（多是 leading 题），回复只要复述问题里的词，keyword_hits 就会误报，以判定模型的结论为准。"
                  "每题都经 packages/worldsim/reference/check_probes.py 按世界模型核对过。"),
        "partner": "旅人（よその土地から来た、あなたとは初対面の者）",
        "scenarios": SCENARIOS,
        "common_questions": COMMON,
        "keywords": KEYWORDS,
    }
    Path(out).write_text(json.dumps(spec, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    n = sum(len(s["questions"]) for s in SCENARIOS)
    print(f"wrote {out}: {len(SCENARIOS)} 个情景，{n} 道专题 + {len(COMMON)} 道通用题 × {len(SCENARIOS)} = {n + len(COMMON) * len(SCENARIOS)} 问（每种写法）")


if __name__ == "__main__":
    main(sys.argv[1])
