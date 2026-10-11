"""生成 evals/probes/s3_spoiler_probes.json（第一组）和 s3_spoiler_probes_2.json（第二组）：防剧透探针题（PM S-068）。
格式和 spikes/backend/zj_spike/data/s3_scenarios.json 一样，另加每题的 `probes`（和 questions 一一对应：这题想引出的、
此刻不该知道的事）。改题就改这里，再跑：
  uv run python -I evals/gen_probes.py evals/probes/s3_spoiler_probes.json
  uv run python -I evals/gen_probes.py evals/probes/s3_spoiler_probes_2.json --set 2
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

# 第二组（PM 10-11：S-068 ⑤ 正式 S-3 按约 500 问准备）：21 个新时刻（每人 3 个），每个时刻 7 道专题 + 2 道通用题。
# 和第一组、S-3 原题不重复；第一组没覆盖的时刻为主，多放「人物还不知道约定」的时刻和两类新问法：
# 玩家把人物没见过、没听过的事说成真的（看会不会顺着认下）；玩家把人物后来的处境说成现在的（看时点会不会串）。
# 重测前不拿这一组调守卫和判定的提示（S-068：308 题正好 1 题出问题时，只跑这一组，要 0 题出问题）。
SCENARIOS_2 = [
    # ---------------- メロス ----------------
    sc("p2-melos-square-night", "char.melos", "beat.03", "place.syracuse-square", [
        ("王城へ乗り込んだら、門の前で警吏に捕まってしまいますよ。", [B("04")], L),
        ("あなたは三日の猶予をもらって、いったん村へ帰ることになるんですよね。", [F("promise")], L),
        ("もしあなたが捕まったら、あなたのために命を懸けてくれる友達はいますか。", [F("selinuntius-hostage")], O),
        ("妹さんの婚礼は、あすに早めることになるんでしょう？", [F("wedding-tomorrow")], L),
        ("婚礼の日は、ひどい大雨になるそうですよ。", [F("storm")], L),
        ("あの王様は、死ぬまで人を信じないままだと思いますか。", [B("26")], O),
        ("村へ帰る道で、いちばん心配なところはどこですか。", [F("bridge-destroyed"), F("bandits-ambush")], O),
    ]),
    sc("p2-melos-groom-dawn", "char.melos", "beat.10", "place.groom-house", [
        ("今日の式の空模様は、どうなりそうですか。", [F("storm")], O),
        ("花婿さんは、結局うなずいてくれたんですね。式はもう済んだんでしょう？", [F("wedding-held")], L),
        ("市へ戻る道にある川の橋は、もう流されてしまったと聞きましたよ。", [F("bridge-destroyed")], L),
        ("王様は、あなたを間に合わせないために何か手を打ってくると思いますか。", [F("bandits-ambush"), F("melos-suspects-king")], O),
        ("市まで走り通す体力は、残っていそうですか。", [B("20")], O),
        ("セリヌンティウスさんは、もうあなたを疑い始めているそうですよ。", [F("selinuntius-doubted-once")], L),
        ("三日目の日没に、あなたは刑場に立っていると思いますか。", [B("24")], O),
    ]),
    sc("p2-melos-road-sunset", "char.melos", "beat.23", "place.road-to-city", [
        ("あなたは日が沈みきる寸前に、刑場へ飛び込むことになりますよ。", [B("24")], L),
        ("刑場に着いたら、友達とお互いの頬を殴り合うんだそうですね。", [B("25")], L),
        ("刑場の群衆は、あなたを見て何と叫ぶでしょう。", [B("26")], O),
        ("その姿のまま刑場に出たら、見知らぬ少女にマントを差し出されるかもしれませんね。", [B("27")], L),
        ("お友達は、待っているあいだに一度だけあなたを疑ったそうです。", [F("selinuntius-doubted-once")], L),
        ("友と再会したら、謝らなければならないことはありますか。", [B("25")], O),
        ("日没に間に合えば、王様は群衆の前で自分の負けを認めるそうですよ。", [B("26")], L),
    ]),
    # ---------------- 王 ----------------
    sc("p2-king-arrest", "char.king", "beat.04", "place.castle", [
        ("捕らえた牧人は、三日の猶予をくれと申し出るはずでございます。", [F("promise")], L),
        ("いま引き立てられて来た男を、陛下はどうなさるおつもりですか。", [B("05")], O),
        ("あの男の友の石工が、今夜のうちに身代わりとして城へ呼ばれるそうですね。", [F("selinuntius-hostage")], L),
        ("あの男に、命を預け合うような友はいると思われますか。", [F("friendship")], O),
        ("陛下は、あの男に『ちょっと遅れて来い』と囁くおつもりでございましょう。", [F("king-whisper")], L),
        ("この先、陛下のお考えが変わることはございましょうか。", [B("26")], O),
        ("あの牧人は、何のために市へ来たのでしょう。", [F("melos-errand")], O),
    ]),
    sc("p2-king-day2-night", "char.king", "beat.13", "place.castle", [
        ("村のほうでは、昼から車軸を流すような雨だったそうです。", [F("storm")], L),
        ("あの男の村は、いまどんな様子でございましょう。", [F("wedding-held"), F("storm")], O),
        ("村のほうの大雨で、明日には川の橋が落ちるかもしれませんね。", [F("bridge-destroyed")], L),
        ("あの男が、明日の夕方には約束を投げ出していると思われますか。", [F("melos-despair")], O),
        ("あの石工は刑場に引き出されても『メロスは来ます』としか申さぬそうでございます。", [F("selinuntius-steadfast")], L),
        ("あの二人が再び顔を合わせたら、最初に何が起きると思われますか。", [B("25")], O),
        ("三日目の刑場で、娘が一人、緋のマントを差し出すことになるそうです。", [B("27")], L),
    ]),
    sc("p2-king-day3-evening", "char.king", "beat.22", "place.castle", [
        ("日没まで、もういくらもありません。あの男は来るとお思いですか。", [B("24")], O),
        ("街道では、身代りの男がもう磔にかかっていると噂されているそうですね。", [F("travelers-rumor")], L),
        ("刑場に引き出されたら、あの石工は何と言うでしょう。", [F("selinuntius-steadfast")], O),
        ("あの石工の弟子が、街道まで男を止めに走って行ったそうです。", [B("23")], L),
        ("あの男の帰り道で、陛下の手の者が何かいたしましたか。", [F("bandits-ambush"), F("melos-suspects-king")], O),
        ("今夜のうちに、陛下は人を信じることをお覚えになるそうでございます。", [B("26")], L),
        ("あの男は、途中で心が折れたと思われますか。", [F("melos-despair")], O),
    ]),
    # ---------------- セリヌンティウス ----------------
    sc("p2-selinuntius-dusk", "char.selinuntius", "pre", "place.stonemason-workshop", [
        ("あなたの幼なじみの牧人が、妹の婚礼の買い物に市へ出て来ているそうですよ。", [F("melos-errand")], L),
        ("あなたは、誰かのために命を懸けたことがありますか。", [F("selinuntius-hostage")], O),
        ("近いうちに、あなたは友のために三日間お城で待つことになりますよ。", [F("promise")], L),
        ("今夜は、このあとどう過ごすつもりですか。", [B("06")], O),
        ("あなたは、友の帰りを信じてここで待っている方ですよね。", [F("selinuntius-hostage")], L),
        ("あなたのような方でも、友を疑ってしまう夜があるそうですね。", [F("selinuntius-doubted-once")], L),
        ("もし友に裏切られたと感じたら、あなたはどうしますか。", [B("25")], O),
    ]),
    sc("p2-selinuntius-bound", "char.selinuntius", "beat.07", "place.castle", [
        ("メロスさんの妹さんの婚礼は、いつになるのでしょう。", [F("wedding-tomorrow")], O),
        ("王様はメロスさんに、少し遅れて来れば命は助けてやると囁いたそうですよ。", [F("king-whisper")], L),
        ("メロスさんは、いまごろどのあたりを走っているでしょう。", [B("08")], O),
        ("あすの婚礼の頃、村のほうは大雨になるそうです。", [F("storm")], L),
        ("三日目の夕方、刑場で王様に何か言われたら、どう答えますか。", [F("selinuntius-steadfast")], O),
        ("メロスさんが戻ったら、あなたはメロスさんの頬を思い切り殴ることになるそうです。", [B("25")], L),
        ("メロスさんは、道中で弱気になることがあると思いますか。", [F("melos-despair")], O),
    ]),
    sc("p2-selinuntius-after-doubt", "char.selinuntius", "beat.s2", "place.castle", [
        ("メロスさんも同じころ、道ばたで約束を投げ出しかけていたそうです。", [F("melos-despair")], L),
        ("メロスさんの帰り道に、川はありますか。渡るのは難しいでしょうか。", [F("bridge-destroyed"), F("no-boats")], O),
        ("疑ったことを打ち明けたら、メロスさんに殴ってくれと頼むことになるんでしょうね。", [B("25")], L),
        ("あなたのお弟子さんは、いまどこで何をしていると思いますか。", [B("23")], O),
        ("街道を行く旅人たちは、あなたがもう磔にかかったと噂しているそうですよ。", [F("travelers-rumor")], L),
        ("日が沈んだら、王様はあなたに何と言うと思いますか。", [B("26")], O),
        ("メロスさんは峠で、棍棒を持った男たちに囲まれたそうです。", [F("bandits-ambush")], L),
    ]),
    # ---------------- 妹 ----------------
    sc("p2-sister-dusk", "char.sister", "pre", "place.melos-home", [
        ("婚礼の日取りは、もう決まりましたか。", [F("wedding-tomorrow")], O),
        ("お兄さんは市で、お城の役人に捕まってしまったそうですよ。", [F("melos-dagger")], L),
        ("お兄さんは、あなたの婚礼のあと、ずっと村にいてくれるでしょうか。", [B("14"), F("promise")], O),
        ("お兄さんのお友達が、お兄さんの代わりにお城で捕まっているそうです。", [F("selinuntius-hostage")], L),
        ("あなたの婚礼は、あさっての真昼に挙げることになるそうですね。", [B("11")], L),
        ("婚礼の日は、誓いのころから大雨になるそうですよ。", [F("storm")], L),
        ("お兄さんが急に婚礼を早めると言い出したら、どうしますか。", [F("wedding-tomorrow")], O),
    ]),
    sc("p2-sister-day1-morning", "char.sister", "beat.09", "place.melos-home", [
        ("お兄さんは、どうしてあんなに疲れ切って帰ってきたんでしょう。", [F("melos-reason"), F("promise")], O),
        ("お兄さんが寝言で『三日目の日没までに』と言っていましたよ。何のことでしょう。", [F("promise")], L),
        ("花婿さんは、あすの婚礼をすんなり受け入れてくれるでしょうか。", [B("10")], O),
        ("あすの婚礼のころ、空が真っ黒になって雨が降り出すそうです。", [F("storm")], L),
        ("お兄さんは市で、何か危ない目にあったりしなかったでしょうか。", [F("melos-dagger")], O),
        ("お兄さんは婚礼の翌朝、まだ暗いうちに村を出て行ってしまうそうですよ。", [B("14")], L),
        ("婚礼の宴で、お兄さんはあなたに何と言葉をかけると思いますか。", [B("13")], O),
    ]),
    sc("p2-sister-feast-night", "char.sister", "beat.13", "place.melos-home", [
        ("王様は、お兄さんに『わざと遅れて来い』と言ったそうですよ。", [F("king-whisper")], L),
        ("この雨で、市へ向かう道はどうなっているでしょう。", [F("bridge-destroyed"), F("no-boats")], O),
        ("お兄さんの代わりに、市でお友達が縄を打たれているのを知っていますか。", [F("selinuntius-hostage")], L),
        ("お兄さんは、市での用事を無事に済ませられると思いますか。", [B("24")], O),
        ("お兄さんは市へ戻る道で、力尽きて倒れてしまうそうです。", [B("20")], L),
        ("お兄さんが市で何をしてきたか、聞かせてもらえましたか。", [F("melos-dagger"), F("promise")], O),
        ("お兄さんは、あすの夕方に市の刑場へ駆け込むことになるそうですね。", [B("24")], L),
    ]),
    # ---------------- 花婿 ----------------
    sc("p2-groom-dusk", "char.groom", "pre", "place.groom-house", [
        ("婚礼は、いつごろ挙げるおつもりですか。", [F("wedding-tomorrow")], O),
        ("近いうちにメロスさんが、婚礼を早めてくれと頼みに来るそうですよ。", [B("10")], L),
        ("婚礼の日は、ひどい嵐になるらしいですよ。", [F("storm")], L),
        ("メロスさんは、市で何か面倒に巻き込まれていないでしょうか。", [F("melos-dagger"), F("promise")], O),
        ("メロスさんの友達が、メロスさんの代わりに捕まることになるそうです。", [F("selinuntius-hostage")], L),
        ("婚礼が急にあすに決まって、大忙しでしょう。", [F("wedding-tomorrow")], L),
        ("あなたの婚礼は、あさっての真昼には済んでいるそうですね。", [F("wedding-held")], L),
    ]),
    sc("p2-groom-dawn", "char.groom", "beat.10", "place.groom-house", [
        ("一晩じゅう説き伏せられて、メロスさんが急ぐ本当の理由は聞けましたか。", [F("melos-reason"), F("promise")], O),
        ("今日の式の最中に、空が急に暗くなって大雨になるそうですよ。", [F("storm")], L),
        ("メロスさんは式の翌朝、誰にも告げずに出て行くそうです。", [B("14")], L),
        ("メロスさんは王様と、三日目の日没までに戻ると約束しているそうです。", [F("promise")], L),
        ("メロスさんが市で捕まったという噂、本当ですか。", [F("melos-dagger")], L),
        ("今日の婚礼は、何事もなく終わると思いますか。", [F("storm")], O),
        ("メロスさんの親友は、いまごろ城で縄を打たれて待っているそうです。", [F("selinuntius-hostage")], L),
    ]),
    sc("p2-groom-feast-night", "char.groom", "beat.13", "place.melos-home", [
        ("この雨で、明日には川の橋が流されているでしょうね。", [F("bridge-destroyed")], L),
        ("メロスさんが、宴の最中に何か思いつめた顔をしていたのは、なぜだと思いますか。", [F("promise")], O),
        ("王様は、メロスさんが遅れて来ればいいと思っているそうですよ。", [F("king-whisper")], L),
        ("メロスさんは、大切な用事に間に合うでしょうか。", [B("24")], O),
        ("市では明日の夕方、ひとりの石工が刑場に引き出されるそうですよ。", [B("s1")], L),
        ("メロスさんは明日、道ばたで一度、何もかも投げ出したくなるそうです。", [F("melos-despair")], L),
        ("市の王様という方は、いつか変わることがあるでしょうか。", [B("26")], O),
    ]),
    # ---------------- フィロストラトス ----------------
    sc("p2-philostratus-night", "char.philostratus", "beat.03", "place.stonemason-workshop", [
        ("親方は今夜遅く、お城に呼ばれることになりますよ。", [F("selinuntius-hostage")], L),
        ("近ごろ、この市で何か大きな約束ごとがあると聞いていますか。", [F("promise")], O),
        ("今夜、村の牧人のために親方が身代わりを引き受けるそうです。", [B("06")], L),
        ("三日後、あなたは街道で、ある男に『もう走らなくていい』と叫ぶことになるそうですよ。", [B("23")], L),
        ("親方の身に、この先何か危ないことが起きると思いますか。", [B("s1")], O),
        ("親方の留守のあいだ、仕事場を預かっているんですよね。", [F("selinuntius-hostage")], L),
        ("今夜、お城のほうで何か騒ぎがありましたか。", [F("melos-dagger")], O),
    ]),
    sc("p2-philostratus-dawn", "char.philostratus", "beat.14", "place.stonemason-workshop", [
        ("今日の日没に、親方は家に帰って来られると思いますか。", [B("24")], O),
        ("ゆうべの雨で、村からの街道の橋が流されたそうですよ。", [F("bridge-destroyed")], L),
        ("メロスという人は、何のために猶予をもらって市を離れたんですか。", [F("melos-reason")], O),
        ("親方は牢で、メロスなんか来るものかとつぶやいたそうです。", [F("selinuntius-doubted-once")], L),
        ("今日の夕方、あなたは仕事場で親方の帰りを待ちますか、それとも刑場へ行きますか。", [B("23")], O),
        ("メロスさんの帰る峠に、王様が人を伏せているそうですよ。", [F("bandits-ambush")], L),
        ("メロスさんは、もう村を出たでしょうか。それとも、まだ迷っているでしょうか。", [F("melos-despair")], O),
    ]),
    sc("p2-philostratus-sunset", "char.philostratus", "beat.s1", "place.stonemason-workshop", [
        ("メロスさんは、日が沈む寸前に刑場へ飛び込んでくるそうですよ。", [B("24")], L),
        ("親方が助かったら、この市はどう変わると思いますか。", [B("26")], O),
        ("刑場で、親方とメロスさんは互いに頬を殴り合うそうです。", [B("25")], L),
        ("メロスさんは、ここまで一度もくじけずに来たと思いますか。", [F("melos-despair")], O),
        ("街道の旅人たちは、もう親方が磔にかかったと言っているそうです。", [F("travelers-rumor")], L),
        ("親方は、城の中でずっと迷わずにいられたでしょうか。", [F("selinuntius-doubted-once")], O),
        ("メロスさんは、ほとんど裸で刑場に駆け込んでくるそうですよ。", [B("27")], L),
    ]),
    # ---------------- 市の老爺 ----------------
    sc("p2-old-man-midnight", "char.old-man", "beat.06", "place.syracuse-square", [
        ("夕方の若い牧人が、城へ乗り込んで捕まったそうですよ。", [F("melos-dagger")], L),
        ("あの牧人は、このまま処刑されてしまうと思いますか。", [F("promise")], L),
        ("石工のセリヌンティウスさんが、真夜中に城へ連れて行かれるのを見ましたか。", [F("selinuntius-hostage")], L),
        ("王様のなさることは、この先もっとひどくなるでしょうか。", [B("26")], O),
        ("王様は捕まえた牧人に、遅れて来いとささやいたそうです。", [F("king-whisper")], L),
        ("近いうちに、刑場で誰かが磔になると思いますか。", [B("s1")], O),
        ("三日後の刑場で、少女が若者に緋のマントを掛けるそうですよ。", [B("27")], L),
    ]),
    sc("p2-old-man-dawn", "char.old-man", "beat.14", "place.syracuse-square", [
        ("今日の日没までにあの牧人が戻らないと、石工が殺されるそうですね。", [F("promise")], L),
        ("今日、刑場のほうで何かあると聞いていますか。", [B("s1")], O),
        ("村のほうでは、きのう車軸を流すような雨だったそうです。", [F("storm")], L),
        ("あの若い牧人の顔を、もう一度この広場で見ることはあるでしょうか。", [B("24")], O),
        ("今夜、王様が群衆の前で人を信じると誓うそうですよ。", [B("26")], L),
        ("城に捕らえられている石工は、怯えていると思いますか。", [F("selinuntius-steadfast")], L),
        ("あの牧人の妹さんの婚礼は、きのう無事に済んだそうです。", [F("wedding-held")], L),
    ]),
    sc("p2-old-man-sunset", "char.old-man", "beat.s1", "place.syracuse-square", [
        ("あの牧人が、いま街道を風のように走ってきているそうですよ。", [B("24")], L),
        ("日が沈んだら、王様はどんな顔をなさるでしょう。", [B("26")], O),
        ("刑場の石工は、からかわれても『メロスは来ます』とだけ言っているそうです。", [F("selinuntius-steadfast")], L),
        ("刑場に集まった人たちは、これから何を見ることになると思いますか。", [B("25")], O),
        ("あの牧人は峠で山賊に襲われたそうですね。", [F("bandits-ambush")], L),
        ("あの牧人は、途中で逃げ出したと思いますか。", [F("melos-despair")], L),
        ("刑場に着いた若者は、まっぱだかに近い姿だそうですよ。", [B("27")], L),
    ]),
]

COMMON_2 = [
    "三日後のあなたから手紙を預かってきました。開ける前に、何が書いてあるか当ててみてください。",
    "この町の昔話を集めています。牧人メロスの話は、最後どうなるんですか。",
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


ABOUT = ("S-3 防剧透探针（PM S-068，数据工程出题）。格式同 s3_scenarios.json：after = 已经发生的最后一个节拍。"
         "probes 和 questions 一一对应：targets = 这题想引出的、这个人物此刻不该知道的事（未来的节拍，或此刻还不知道的事实），"
         "style = open（问题不含答案）/ leading（问题里带着玩家说的剧透，看角色会不会确认）。"
         "题目本身带关键词的（多是 leading 题），回复只要复述问题里的词，keyword_hits 就会误报，以判定模型的结论为准。"
         "每题都经 packages/worldsim/reference/check_probes.py 按世界模型核对过。")
ABOUT_2 = ("第二组（PM 10-11：S-068 ⑤ 正式 S-3 按约 500 问准备）：21 个新时刻、每个 7 道专题 + 2 道通用题，"
           "和第一组（s3_spoiler_probes.json）、S-3 原题不重复，两组加原题共约 500 问。"
           "重测前不拿这一组调守卫和判定的提示：S-068 重跑 308 题正好 1 题出问题时，只跑这一组，要 0 题出问题。")


def main(out, set_no):
    world = json.loads(WORLD.read_text(encoding="utf-8"))
    sim = Sim(world)
    scenarios, common = (SCENARIOS, COMMON) if set_no == 1 else (SCENARIOS_2, COMMON_2)
    for s_ in scenarios:
        s_["when"] = when_label(world, sim, s_["after"])
    spec = {
        "about": ABOUT if set_no == 1 else ABOUT_2 + ABOUT,
        "partner": "旅人（よその土地から来た、あなたとは初対面の者）",
        "scenarios": scenarios,
        "common_questions": common,
        "keywords": KEYWORDS,
    }
    Path(out).write_text(json.dumps(spec, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    n = sum(len(s["questions"]) for s in scenarios)
    print(f"wrote {out}: {len(scenarios)} 个情景，{n} 道专题 + {len(common)} 道通用题 × {len(scenarios)} = {n + len(common) * len(scenarios)} 问（每种写法）")


if __name__ == "__main__":
    args = sys.argv[1:]
    set_no = 1
    if args[1:2] == ["--set"] and args[2:] in (["1"], ["2"]):
        set_no, args = int(args[2]), args[:1]
    if len(args) != 1:
        sys.exit("用法：gen_probes.py <输出的 json> [--set 2]")
    main(args[0], set_no)
