"""Beer profiles and deterministic quiz scoring. All associations are playful."""
import secrets

STYLES = {
 'lager': ('Лёгкий лагер', [1,1,0,1,0,0], 'Лёгкий, освежающий, сдержанная горечь'),
 'pilsner': ('Пильзнер', [2,1,0,1,0,0], 'Сухой и хрустящий, с заметным хмелем'),
 'wheat': ('Пшеничное', [1,2,0,2,0,2], 'Мягкость и фруктово-пряные оттенки'),
 'pale': ('Pale Ale', [2,1,0,2,0,2], 'Хмель, цитрусы и умеренная насыщенность'),
 'ipa': ('IPA', [4,1,0,2,0,3], 'Выраженная хмелевая горечь и фруктовый аромат'),
 'amber': ('Янтарный эль', [2,2,0,3,1,0], 'Солод, хлебная корочка и карамель'),
 'porter': ('Портер', [2,2,0,3,3,0], 'Тёмный солод и поджаренные ноты'),
 'stout': ('Стаут', [2,1,0,3,4,0], 'Кофейные и жареные оттенки'),
 'sour': ('Фруктовый кислый эль', [1,1,4,2,0,4], 'Ягодная кислинка и фруктовый профиль'),
}
# question: (id, title, kind, [(label, axis values, style bonuses)])
QUESTIONS = [
 ('bitter','Горечь — удовольствие или наказание?','taste', [('Не хочу',{0:0},{}),('Совсем немного',{0:1},{}),('Заметную',{0:2},{}),('Люблю сильно',{0:4},{})]),
 ('table','Что первым возьмёшь со стола?','taste',[('Хлебную корочку',{1:1,4:1},{}),('Карамель',{1:3},{}),('Чёрный кофе',{4:4,1:0},{}),('Цитрусы',{5:3},{}),('Ягоды с кислинкой',{2:3,5:3},{})]),
 ('body','Какое ощущение хочется?','taste',[('Лёгкое и освежающее',{3:1},{}),('Среднее',{3:2},{}),('Насыщенное',{3:4},{})]),
 ('acid','Кислинка — это как?','taste',[('Не люблю',{2:0},{}),('Немного нравится',{2:1},{}),('Чем ярче, тем лучше',{2:4},{})]),
 ('sweet','Сладость нужна?','taste',[('Сухое',{1:0},{}),('Немного',{1:1},{}),('Заметная',{1:3},{})]),
 ('fruit','Фрукты и пряности?','taste',[('Без них',{5:0},{}),('Цитрусы',{5:3},{}),('Тропики',{5:4},{}),('Банан и пряности',{5:2},{'wheat':2}),('Ягоды',{5:3},{})]),
 ('season','В какое время года отправим твоё пиво?','association',[('Лето',{}, {'lager':2}),('Осень',{}, {'amber':2}),('Зима',{}, {'porter':2,'stout':2}),('Весна',{}, {'wheat':2})]),
 ('film','Какой фильм включаем?','association',[('Форсаж',{}, {'lager':3}),('Приключения',{}, {'pale':1}),('Нуар',{}, {'porter':2}),('Без предпочтений',{}, {})]),
 ('place','Где открывается сцена?','association',[('Ростов-на-Дону',{}, {'lager':2}),('Побережье',{}, {'lager':2}),('Лесной дом',{}, {'amber':2}),('Большой город',{}, {'pale':1})]),
 ('music','Какой саундтрек?','association',[('Лёгкий поп',{}, {'lager':1}),('Рок',{}, {'ipa':1}),('Джаз',{}, {'porter':1}),('Электроника',{}, {'pale':1})]),
 ('evening','Как выглядит вечер?','association',[('Пикник',{}, {'wheat':1}),('Настолки',{}, {'amber':1}),('Плед и книга',{}, {'stout':1}),('Эксперимент',{}, {})]),
 ('card','Какую открытку выберешь?','association',[('Солнце и вода',{}, {'lager':1}),('Золотые листья',{}, {'amber':1}),('Дождливый город',{}, {'porter':1}),('Яркие фрукты',{}, {'sour':1,'wheat':1})]),
]

def allowed_styles(c):
    return [k for k in STYLES if not (k=='ipa' and c.get('no_bitter')) and not (k=='sour' and c.get('no_sour')) and not (k in ('porter','stout') and c.get('no_roast'))]

def quiz(answers, route, c):
    if not isinstance(answers,dict): raise ValueError('Некорректные ответы теста')
    if route not in ('taste','association','mixed'): raise ValueError('Неизвестный маршрут')
    axes=[[] for _ in range(6)]; bonus={k:0 for k in STYLES}; labels=[]
    for key,title,kind,options in QUESTIONS:
        if route!='mixed' and kind!=route: continue
        if route=='mixed' and key in ('sweet','fruit','evening','card'): continue
        value=answers.get(key)
        if value is None or value=='': continue
        if type(value) is not int or not 0<=value<len(options): raise ValueError('Неверный ответ теста')
        label,values,points=options[value]; labels.append(label)
        for axis,v in values.items(): axes[axis].append(v)
        for style,v in points.items(): bonus[style]+=v
        if key=='bitter' and value==0: c={**c,'no_bitter':True}
        if key=='acid' and value==0: c={**c,'no_sour':True}
    if not labels: raise ValueError('Ответь хотя бы на один вопрос')
    has_taste=any(axes); top=max(bonus.values()) or 1
    def score(k):
        ds=[abs(sum(a)/len(a)-STYLES[k][1][i]) for i,a in enumerate(axes) if a]
        t=100*(1-sum(ds)/len(ds)/4) if ds else 0
        g=100*bonus[k]/top
        return t if route=='taste' else g if route=='association' or not has_taste else .8*t+.2*g
    ids=sorted(allowed_styles(c),key=score,reverse=True)[:3]
    prefix='Игровая ассоциация' if route=='association' or not has_taste else 'По вкусовым ответам и ассоциациям'
    explanation=prefix+': '+', '.join(labels)+'.'
    if answers.get('film')==0 and route!='taste': explanation+=' «Форсаж → Corona» — игровая отсылка, состав проверяй по этикетке.'
    if answers.get('place')==0 and route!='taste': explanation+=' «Ростов → Дон» — игровая отсылка.'
    return {'styles':[{'id':k,'name':STYLES[k][0],'description':STYLES[k][2]} for k in ids], 'explanation':explanation, 'constraints':c}

def derangement(ids):
    if len(ids)<3: raise ValueError('Нужно минимум 3 участника')
    rng=secrets.SystemRandom(); out=list(ids)
    while True:
        rng.shuffle(out)
        if all(a!=b for a,b in zip(ids,out)): return list(zip(ids,out))
