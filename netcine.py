from urllib.parse import urlparse, quote_plus
import requests
from bs4 import BeautifulSoup
import re
import json

def catalog_search(text):
    catalog = []
    url = 'https://v3.sg.media-imdb.com/suggestion/x/' + quote_plus(text) + '.json?includeVideos=1'
    try:
        data = requests.get(url).json()['d']
        for i in data:
            try:
                poster = i['i']['imageUrl']
                id = i['id']
                title = i['l']
                tp = i['qid']
                if 'series' in tp.lower():
                    tp = 'series'
                y = i['y']
                if 'tt' in id:
                    catalog.append({
                        "id": id,
                        "type": tp,
                        "title": title,
                        "year": int(y),
                        "poster": poster
                    })
            except:
                pass
    except:
        pass
    return catalog

def resolve_stream(url):
    parsed_url = urlparse(url)
    referer = '%s://%s/'%(parsed_url.scheme,parsed_url.netloc)        
    stream = ''
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, como Gecko) Chrome/88.0.4324.96 Safari/537.36"}
    headers.update({'Cookie': 'XCRF%3DXCRF', 'Referer': referer})
    try:
        r = requests.get(url,headers=headers)
        src = r.text
        soup = BeautifulSoup(src, 'html.parser')
        url = soup.find('div', {'id': 'content'}).find_all('a')[0].get('href', '') 
    except:
        pass        
            
    try:
        r = requests.get(url,headers=headers)
        src = r.text
        regex_pattern = r'<source[^>]*\s+src="([^"]+)"'
        alto = []
        baixo = []
        matches = re.findall(regex_pattern, src)
        for match in matches:
            if 'ALTO' in match:
                alto.append(match)
            if 'alto' in match:
                alto.append(match)
            if 'BAIXO' in match:
                baixo.append(match)
            if 'baixo' in match:
                baixo.append(match)  
        if alto:
            stream = alto[-1]
            if ' ' in stream:
                stream = ''
        elif baixo:
            stream = baixo[-1]
            if ' ' in stream:
                stream = ''            
    except:
        pass
    return stream, headers

def search_term(imdb):
    url = 'https://www.imdb.com/pt/title/%s/'%imdb
    keys = []
    try:
        r = requests.get(url,headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:134.0) Gecko/20100101 Firefox/134.0', 'Accept-Language': 'pt-BR,pt;q=0.8,en-US;q=0.5,en;q=0.3'})
        src = r.text
        script = re.findall('json">(.*?)</script>', src, re.DOTALL)[0]
        title = re.findall('<title>(.*?)</title>', src)[0]
        data = json.loads(script)
        name = data.get('name', '')
        name2 = data.get('alternateName', '')
        if name:
            keys.append(name)
        if name2:
            keys.append(name2)
        try:
            year_ = re.findall(r'Série de TV (.*?)\)', title)
            if not year_:
                year_ = re.findall(r'\((.*?)\)', title)
            if year_:
                year = year_[0]
                try:
                    year = year.split('–')[0]
                except:
                    pass
        except:
            year = ''       

    except:
        pass
    return keys, year

def opcoes_filmes(url, headers, host):
    player_links = []
    try:
        headers.update({'Cookie': 'XCRF%3DXCRF'})
        r = requests.get(url, headers=headers)
        src = r.text
        soup = BeautifulSoup(src, 'html.parser')
        player = soup.find('div', {'id': 'player-container'})
        botoes = player.find('ul', {'class': 'player-menu'})
        op = botoes.findAll('li')
        op_list = []
        if op:
            for i in op:
                a = i.find('a')
                id_ = a.get('href', '').replace('#', '')
                op_name = a.text.strip().upper()
                op_list.append((op_name, id_))
        
        if op_list:
            for name, id_ in op_list:
                iframe = player.find('div', {'class': 'play-c'}).find('div', {'id': id_}).find('iframe').get('src', '')
                link = host + iframe if not 'streamtape' in iframe else iframe
                
                if not 'streamtape' in link:
                    player_links.append({'name': name.replace(' 1', ''), 'url': link})
    except:
        pass
    return player_links

def check_item(search,headers,year_imdb,text):
    r = requests.get(search,headers=headers)
    src = r.text
    soup = BeautifulSoup(src,'html.parser')
    box = soup.find("div", {"id": "box_movies"})
    movies = box.findAll("div", {"class": "movie"})
    count = 0
    for i in movies:
        try:
            year = i.find('span', {'class': 'year'}).text
            year = year.replace('–', '')
        except:
            year = ''
        name = i.find('h2').text
        try:
            name = name.decode('utf-8')
        except: pass
        try:
            name = name.decode()
        except: pass           
        if ':' in text:
            text_search = text.split(':')[1].replace(' ', '').lower()
            name_search = name.replace(' ', '').lower()
            if text_search in name_search:
                count += 1
                break
        else:
            if str(year_imdb) in str(year):
                count += 1
                break
            elif str(int(year_imdb) + 1) in str(year):
                count += 1         
                break
            elif str(int(year_imdb) - 1) in str(year):
                count += 1
                break
    if count > 0:
        return movies
    else:
        return []        

def scrape_search(host,headers,text,alternate,year_imdb,type):
    text = text.replace('&amp;', '&')
    alternate = alternate.replace('&amp;', '&')
    url = requests.get(host,headers=headers).url
    url_parsed = urlparse(url)
    new_host = url_parsed.scheme + '://' + url_parsed.hostname + '/'
    try:
        keys_search = text.split(' ')
        search_ = ' '.join(keys_search[:-1]) if len(keys_search) > 2 else text
    except: search_ = text
    try:
        if len(search_.split(' ')) > 2 and ':' in text:
            search_ = text.split(': ')[1]
    except: pass   
    url_search = new_host + '?s=' + quote_plus(search_)
    headers.update({'Cookie': 'XCRF%3DXCRF'})
    movies = check_item(url_search,headers,year_imdb,text)
    if not movies:
        try:
            if ':' in text:
                param_search = text.split(':')[1]
                url_search2 = new_host + '?s=' + quote_plus(param_search)
                movies = check_item(url_search2,headers,year_imdb,text)
        except: movies = []
    for i in movies:
        name = i.find('h2').text
        try: name = name.decode('utf-8')
        except: pass
        name_backup = name
        text_backup = text
        textalternate_backup = alternate
        try:
            keys = name.split(' ')
            name2 = ' '.join(keys[:-1])
        except: name2 = ''
        try:
            keys2 = text.split(' ')
            text2 = ' '.join(keys2[:-1])
        except: text2 = ''                           
        try:
            year = i.find('span', {'class': 'year'}).text
            year = year.replace('–', '')
        except:
            year = ''
        try:
            text = text.lower().replace(':', '')
        except: pass
        try:
            textalternate = alternate.lower().replace(':', '')
        except: pass        
        try:
            name = name.lower().replace(':', '')
        except: pass
        try:
            text2 = text2.lower()
        except: pass
        try:
            name2 = name2.lower()
        except: pass
        try:
            name3 = name2.replace(' –', ':')
        except: name3 = ''
        try:
            count_text = len(name3.split(' '))
        except: count_text = 0
        try:
            if ':' in name_backup:
                name4 = name_backup.split(': ')[1].lower()
            else: name4 = ''
        except: name4 = ''
        try:
            if ':' in text_backup:
                text3 = text_backup.split(': ')[1].lower()
            else: text3 = ''
        except: text3 = ''
        try:
            if ':' in textalternate_backup:
                textalternate2 = textalternate_backup.split(': ')[1].lower()
            else: textalternate2 = ''
        except: textalternate2 = ''            
        if '&' in text:
            text4 = text.replace('&', 'e')
        else: text4 = text
        if '&' in name and not '&amp;' in name:
            name5 = name.replace('&', 'e')
        else: name5 = name
        if ' e ' in text:
            text5 = text.replace(' e ', ' & ')
        else: text5 = text 
        if ' e ' in name:
            name6 = name.replace(' e ', ' & ')
        else: name6 = name
        try:
            count_text2 = len(text.split(' '))
        except: count_text2 = 0
        try:
            img = i.find('div', {'class': 'imagen'})
            link = img.find('a').get('href', '')
        except: link = ''
        count_name_ = len(name)
        count_text_ = len(text)
        if type == 'tvshows' and '/tvshows/' in link:
            if text in name and str(year_imdb) in str(year) or text2 in name2 and str(year_imdb) in str(year):
                return link, new_host
            elif text2 in name3 and str(year_imdb) in str(year):
                return link, new_host 
            elif text2 in name3 and str(int(year_imdb) + 1) in str(year) and count_text > 1 and not count_name_ > count_text_:     
                return link, new_host
            elif text2 in name3 and str(int(year_imdb) - 1) in str(year) and count_text > 1 and not count_name_ > count_text_:    
                return link, new_host
            elif text3 in name4 and str(year_imdb) in str(year) and text3 and name4:
                return link, new_host
            elif text4 in name5 and str(year_imdb) in str(year) and text4 and name5:               
                return link, new_host
            elif len(text5) == len(name6) and str(year_imdb) in str(year) and text5 and name6:              
                return link, new_host
            elif textalternate in name and str(year_imdb) in str(year) or textalternate2 in name4 and str(year_imdb) in str(year):
                return link, new_host
            elif text in name and str(int(year_imdb) + 1) in str(year) and count_text2 > 0 and not count_name_ > count_text_:
                return link, new_host
            elif text in name and str(int(year_imdb) -1) in str(year) and count_text2 > 0 and not count_name_ > count_text_:
                return link, new_host              
        elif type == 'movies' and not '/tvshows/' in link: 
            if text in name and str(year_imdb) in str(year) or text2 in name2 and str(year_imdb) in str(year):
                return link, new_host
            elif text2 in name3 and str(year_imdb) in str(year):
                return link, new_host 
            elif text2 in name3 and str(int(year_imdb) + 1) in str(year) and count_text > 1 and not count_name_ > count_text_:     
                return link, new_host
            elif text2 in name3 and str(int(year_imdb) - 1) in str(year) and count_text > 1 and not count_name_ > count_text_:    
                return link, new_host
            elif text3 in name4 and str(year_imdb) in str(year) and text3 and name4:
                return link, new_host
            elif text4 in name5 and str(year_imdb) in str(year) and text4 and name5:               
                return link, new_host
            elif len(text5) == len(name6) and str(year_imdb) in str(year) and text5 and name6:              
                return link, new_host
            elif textalternate in name and str(year_imdb) in str(year) or textalternate2 in name4 and str(year_imdb) in str(year):
                return link, new_host
            elif text in name and str(int(year_imdb) + 1) in str(year) and count_text2 > 0 and not count_name_ > count_text_:
                return link, new_host
            elif text in name and str(int(year_imdb) -1) in str(year) and count_text2 > 0 and not count_name_ > count_text_:
                return link, new_host                                                            
    return '', ''   

def search_link(id):
    streams = []
    host = 'https://netcinez.si/'
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, como Gecko) Chrome/88.0.4324.96 Safari/537.36"}
    
    try:
        if ':' in id: # Lógica para Séries
            parts = id.split(':')
            imdb, season, episode = parts[0], parts[1], parts[2]
            search_text, year_imdb = search_term(imdb)
            if search_text and year_imdb:
                text, alternate = search_text[-1], search_text[0]
                link, new_host = scrape_search(host, headers, text, alternate, year_imdb, 'tvshows')
                if '/tvshows/' in link:
                    r = requests.get(link, headers=headers)
                    soup = BeautifulSoup(r.text, 'html.parser')
                    s = soup.find('div', {'id': 'movie'}).find('div', {'class': 'post'}).find('div', {'id': 'cssmenu'}).find('ul').findAll('li', {'class': 'has-sub'})
                    for n, i in enumerate(s, 1):
                        if int(season) == n:
                            e = i.find('ul').findAll('li')
                            for n_ep, i_ep in enumerate(e, 1):
                                if int(episode) == n_ep:
                                    link_ep = i_ep.find('a').get('href')
                                    player_options = opcoes_filmes(link_ep, headers, new_host)
                                    for option in player_options:
                                        stream_url, stream_headers = resolve_stream(option['url'])
                                        if stream_url:
                                            streams.append({
                                                "name": f"Netcine - {option['name']}",
                                                "url": stream_url,
                                                "behaviorHints": {"notWebReady": True, "proxyHeaders": {"request": stream_headers}}
                                            })
                                    break
                            break   
        else: # Lógica para Filmes
            imdb = id
            search_text, year_imdb = search_term(imdb)
            if search_text and year_imdb:
                text, alternate = search_text[-1], search_text[0]
                link, new_host = scrape_search(host, headers, text, alternate, year_imdb, 'movies')
                if link and not '/tvshows/' in link:
                    player_options = opcoes_filmes(link, headers, new_host)
                    for option in player_options:
                        stream_url, stream_headers = resolve_stream(option['url'])
                        if stream_url:
                            streams.append({
                                "name": f"Netcine - {option['name']}",
                                "url": stream_url,
                                "behaviorHints": {"notWebReady": True, "proxyHeaders": {"request": stream_headers}}
                            })
    except:
        pass
    return streams