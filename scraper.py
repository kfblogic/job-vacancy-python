from singletons.cloudscrapper import CloudScraper
from bs4 import BeautifulSoup
from helpers.response import ResponseHelper

import re, json, math, traceback

class Scraper:
    def __init__(self):
        self.glints_url = "https://glints.com/id/opportunities/jobs/explore"
        self.jobstreet_url = "https://id.jobstreet.com/id/{work}-jobs/in-Indonesia"
        self.karir_url = "https://karir.com/search-lowongan"
        self.api_karir_url = "https://gateway2-beta.karir.com/v2/search/opportunities"

    def search_glints2(
        self,
        work="Programmer",
        job_type="",
        work_option="",
        location_id="all",
        page=1,
        cookies_file="config/glints.json",
    ):
        """
        Versi GraphQL — memanggil searchJobsV3 agar tidak scrape HTML.
        Tetap mengembalikan struktur:
        {
        'jobs': [...],
        'pagination': {'current_page', 'last_page', 'has_next'}
        }
        """
        # =======================
        # 0) Konversi parameter
        # =======================
        # Mapping enum GraphQL
        jobType_options = {
            "": "",
            "fulltime": "FULL_TIME",
            "kontrak": "CONTRACT",
            "magang": "INTERNSHIP",
            "parttime": "PART_TIME",
            "freelance": "PROJECT_BASED",
        }
        work_options = {
            "": "",
            "onsite": "ONSITE",
            "hybird": "HYBIRD",
            "remote": "REMOTE",
        }
        # *Jika ingin filter lokasi via GraphQL, cek skema terbaru Glints; contoh query yang kamu kirim tidak
        #  menyertakan filter lokasi. Sementara ini, kita tidak kirim filter lokasi ke GraphQL.*

        # Validasi & normalisasi
        try:
            page = int(page)
            if page <= 0:
                return ResponseHelper.failure_response("Page must be a positive integer.")
        except ValueError:
            return ResponseHelper.failure_response("Invalid page parameter. Must be an integer.")

        job_types_input = [j.strip().lower() for j in job_type.split(",") if j.strip()]
        option_works_input = [w.strip().lower() for w in work_option.split(",") if w.strip()]

        invalid_job_types = [j for j in job_types_input if j not in jobType_options]
        invalid_option_works = [w for w in option_works_input if w not in work_options]
        if invalid_job_types:
            return ResponseHelper.failure_response(
                f"Invalid job_type: {invalid_job_types}. valid options: {list(jobType_options)}"
            )
        if invalid_option_works:
            return ResponseHelper.failure_response(
                f"Invalid work_option: {invalid_option_works}. valid options: {list(work_options)}"
            )

        gql_job_types = [jobType_options[j] for j in job_types_input if jobType_options[j]]
        gql_work_arrangement = [work_options[k] for k in option_works_input if work_options[k]]
        # (opsional) work arrangement bisa dipakai jika skema GraphQL mendukung; query contoh tidak memakainya
        # maka kita biarkan tidak dipakai dulu.

        page_size = 30

        # =======================
        # 1) Siapkan GraphQL
        # =======================
        GLINTS_GRAPHQL_ENDPOINT = "https://glints.com/api/v2-alc/graphql?op=searchJobsV3"  # ganti jika berbeda
        QUERY = """
        query searchJobsV3($data: JobSearchConditionInput!) {
        searchJobsV3(data: $data) {
            jobsInPage {
            id
            title
            workArrangementOption
            shouldShowSalary
            salaryEstimate { minAmount maxAmount CurrencyCode __typename }
            company { id name logo __typename }
            city { id name __typename }
            country { code name __typename }
            location { id name formattedName latitude longitude __typename }
            minYearsOfExperience
            maxYearsOfExperience
            source
            createdAt
            updatedAt
            __typename
            }
            hasMore
            __typename
        }
        }
        """.strip()

        variables = {
            "data": {
                "SearchTerm": work,
                "CountryCode": "ID",
                "type": gql_job_types,           # boleh kosong []
                "includeExternalJobs": True,
                "pageSize": page_size,
                "page": page,
                "workArrangementOptions": gql_work_arrangement
            }
        }
        payload = {
            "operationName": "searchJobsV3",
            "variables": variables,
            "query": QUERY,
        }

        # =======================
        # 2) Eksekusi request
        # =======================
        try:
            scraper = CloudScraper.get_instance(cookies_file)
            headers = {
                "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                            "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
                "accept-language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
                "referer": "https://glints.com/",
                "origin": "https://glints.com",
            }

            resp = scraper.post(GLINTS_GRAPHQL_ENDPOINT, data=json.dumps(payload), headers=headers)
            print(resp.text)
            resp.raise_for_status()
            data = resp.json()

            # Error GraphQL?
            if not isinstance(data, dict) or "data" not in data:
                return ResponseHelper.failure_response("Unexpected response from Glints GraphQL.")
            if "errors" in data and data["errors"]:
                return ResponseHelper.failure_response(f"GraphQL errors: {data['errors']}")

            res = data["data"]["searchJobsV3"]
            jobs = res.get("jobsInPage") or []
            has_more = bool(res.get("hasMore"))

            # =======================
            # 3) Normalisasi hasil
            # =======================
            out = []
            for j in jobs:
                # Salary
                salary = "N/A"
                if j.get("shouldShowSalary"):
                    est = j.get("salaryEstimate") or {}
                    mn, mx = est.get("minAmount"), est.get("maxAmount")
                    cur = est.get("CurrencyCode") or ""
                    if mn is not None or mx is not None:
                        left = f"{int(mn):,}".replace(",", ".") if isinstance(mn, (int, float)) else ""
                        right = f"{int(mx):,}".replace(",", ".") if isinstance(mx, (int, float)) else ""
                        rng = f"{left} - {right}".strip(" -")
                        salary = f"{cur} {rng}".strip()

                # Lokasi
                loc = j.get("location") or {}
                city = (j.get("city") or {}).get("name")
                country = (j.get("country") or {}).get("name")
                location_text = loc.get("formattedName") or city or country or "N/A"

                # Company/logo
                comp = j.get("company") or {}
                company_name = comp.get("name") or "N/A"
                company_logo = comp.get("logo") or "N/A"

                # Link detail (heuristik umum Glints)
                job_id = j.get("id")
                link = f"https://glints.com/id/opportunities/jobs/{job_id}" if job_id else "N/A"

                out.append({
                    "title": j.get("title") or "N/A",
                    "salary": salary,
                    "location": location_text,
                    "company_name": company_name,
                    "company_logo": company_logo,
                    "link": link,
                    "source": "Glints",
                })

            # =======================
            # 4) Pagination
            # =======================
            current_page = page
            last_page = current_page + 1 if has_more else current_page
            has_next = has_more

            return ResponseHelper.success_response("Success find job", {
                "jobs": out,
                "pagination": {
                    "current_page": current_page,
                    "last_page": last_page,
                    "has_next": has_next,
                },
                # tambahkan sedikit jejak debug agar bisa dilihat dengan ?debug=1 dari route
                "_debug": {
                    "endpoint": GLINTS_GRAPHQL_ENDPOINT,
                    "page_size": page_size,
                    "sent_job_types": gql_job_types,
                    "work_option": option_works_input,  # terekam meski tdk dipakai di query
                    "resolved_url": getattr(resp, "url", GLINTS_GRAPHQL_ENDPOINT),
                    "items": len(out),
                    "has_more": has_more,
                }
            })

        except Exception as e:
            traceback.print_tb(e.__traceback__)
            return ResponseHelper.failure_response(f"Glints GraphQL error: {str(e)}")


    def search_glints(self, work = "Programmer", job_type = "", work_option = "", location_id = "all", page = 1, cookies_file='config/glints.json'):
        jobType_options = {
            "": "",
            "fulltime": "FULL_TIME",
            "kontrak": "CONTRACT",
            "magang": "INTERNSHIP",
            "parttime": "PART_TIME",
            "freelance": "PROJECT_BASED"
        }

        work_options = {
            "": "",
            "onsite": "ONSITE",
            "hybird": "HYBIRD",
            "remote": "REMOTE"
        }

        locationId_options = {
            "all": "All+Cities/Provinces",
            "jabodetabek": "JABODETABEK",
            "jakarta": "78d63064-78a1-4577-8516-036a6c5e903e",
            "banten": "82f248c3-3fb3-4600-98fe-4afb47d7558d",
            "jawatimur": "bc26ec98-d599-44cb-84e7-c92f6d87e102",
            "jakartaselatan": "078b37b2-e791-4739-958e-c29192e5df3e",
            "jakartabarat": "af0ed74f-1b51-43cf-a14c-459996e39105",
            "tangerang": "ae3c458e-5947-4833-8f1b-e001ce2fad1d",
            "jakartautara": "ea61f4ac-5864-4b2b-a2c8-aa744a2aafea",
            "surabaya": "0822446a-8784-4af4-bc88-9f9294fca382"
        }

        job_types_input = [j.strip().lower() for j in job_type.split(',') if j.strip()]
        option_works_input = [w.strip().lower() for w in work_option.split(',') if w.strip()]

        invalid_job_types = [j for j in job_types_input if j not in jobType_options]
        invalid_option_works = [w for w in option_works_input if w not in work_options]

        if invalid_job_types:
            return ResponseHelper.failure_response(f"Invalid job_type: {invalid_job_types}. valid options: {list(jobType_options)}")

        if invalid_option_works:
            return ResponseHelper.failure_response(f"Invalid work_option: {invalid_option_works}. valid options: {list(work_options)}")
        
        if location_id.lower() not in list(locationId_options):
            return ResponseHelper.failure_response(f"Invalid location_id: {location_id}. valid_options: {list(locationId_options)}")
        
        try:
            page = int(page)
            if page <= 0:
                return ResponseHelper.failure_response("Page must be a positive integer.")
        except ValueError:
            return ResponseHelper.failure_response("Invalid page parameter. Must be an integer.")
        

        job_types_param = ','.join([jobType_options[j] for j in job_types_input if jobType_options[j]])
        option_works_param = ','.join([work_options[w] for w in option_works_input if work_options[w]])

        
        params = {
            "keyword": work,
            "country": "ID",
            "locationName": locationId_options[location_id.lower()],
            "jobTypes": job_types_param,
            "workArrangementOptions": option_works_param,
            "lowestLocationLevel": "1",
            "page": page
        }

        scraper = CloudScraper.get_instance(cookies_file)
        response = scraper.get(self.glints_url, params=params)
        response.raise_for_status()
        html = response.text
        soup = BeautifulSoup(html, 'html.parser')
        try:
            with open('test.txt', 'w', encoding='utf-8') as f:
                f.write(soup.prettify())
        except OSError:
            pass  # Skip di Vercel (read-only filesystem)
        job_cards = soup.find_all('div', class_=re.compile(r'JobCardsc__JobcardContainer'))
        print(params)
        print(response.url)
        if not job_cards:
            return ResponseHelper.failure_response(f'Tidak ada lowongan pekerjaan yang tersedia untuk `{work}` di website Glints')

        results = []
        for job_card in job_cards:
            title_tag = job_card.find('h2')
            title = title_tag.get_text(strip=True) if title_tag else 'N/A'

            salary_tag = job_card.find('span', class_=re.compile(r'CompactOpportunityCardsc__SalaryWrapper'))
            salary = salary_tag.get_text(strip=True).replace('\u00a0', '') if salary_tag else 'N/A'

            location_tag = job_card.find('div', class_=re.compile(r'CardJobLocation__LocationWrapper'))

            locations = location_tag.find_all('a')
            full_location = ', '.join([loc.get_text(strip=True) for loc in locations])

            link_tag = job_card.find('a', href=True)
            link = f"https://glints.com{link_tag['href']}" if link_tag else 'N/A'

            company_name_tag = job_card.find('a', class_=re.compile(r'CompactOpportunityCardsc__CompanyLink'))
            company_name = company_name_tag.get_text(strip=True) if company_name_tag else 'N/A'

            company_logo_tag = job_card.find('img', class_=re.compile(r'CompactOpportunityCardsc__CompanyAvatar'))
            company_logo = company_logo_tag['src'] if company_logo_tag and company_logo_tag.has_attr('src') else 'N/A'

            results.append({
                'title': title,
                'salary': salary,
                'location': full_location,
                'company_name': company_name,
                'company_logo': company_logo,
                'link': link,
            })
        jobs_per_page = 30  # Estimasi jumlah per halaman
        current_page = page
        has_next = len(results) == jobs_per_page  # Jika jumlah hasil = batas, kemungkinan masih ada
        last_page = current_page + 1 if has_next else current_page

        return ResponseHelper.success_response('Success find job', {
            'jobs': results,
            'pagination': {
                'current_page': current_page,
                'last_page': last_page,
                'has_next': has_next
            }
        })
    
    def search_jobstreet(self, work = "Programmer", work_option = "", job_type = "", page = 1, cookies_file = 'config/jobstreet.json'):
        jobType_options = {
            "": "",
            "fulltime": "242",
            "parttime": "243",
            "kontrak": "244",
            "freelance": "245"
        }

        work_options = {
            "": "",
            "onsite": "1",
            "hybird": "2",
            "remote": "3"
        }
        job_types_input = [j.strip().lower() for j in job_type.split(',') if j.strip()]

        option_works_input = [w.strip().lower() for w in work_option.split(',') if w.strip()]
        option_works_param = ','.join([work_options[w] for w in option_works_input if work_options[w]])

        invalid_job_types = [j for j in job_types_input if j not in jobType_options]
        invalid_option_works = [w for w in option_works_input if w not in work_options]


        if invalid_option_works:
            return ResponseHelper.failure_response(f"Invalid option_work: {invalid_option_works}. valid options: {list(work_option)}")
        
        if invalid_job_types:
            return ResponseHelper.failure_response(f"Invalid job_type: {invalid_job_types}. valid options: {list(jobType_options)}")
        
        url = self.jobstreet_url.format(work = work)
        params = {
            "worktype": option_works_param,
            "page": page
        }

        try:
            scraper = CloudScraper.get_instance(cookies_file)

            response = scraper.get(url, params = params)
            response.raise_for_status()
            html = response.text

            soup = BeautifulSoup(html, 'html.parser')

            total_jobs_tag = soup.find('div', attrs={"data-automation": "totalJobsMessage"})
            total_jobs = total_jobs_tag.find('span').get_text(strip=True)

            job_cards = soup.find_all('article', attrs={"data-automation": "normalJob"})
            if not job_cards:
                return ResponseHelper.failure_response(f'Tidak ada lowongan pekerjaan yang tersedia untuk `{work}` di website JobStreet')

            results = []
            for job_card in job_cards:
                title_tag = job_card.find('a', attrs={"data-automation": "jobTitle"})
                title = title_tag.get_text(strip=True) if title_tag else 'N/A'

                company_name_tag = job_card.find('a', attrs={"data-automation": "jobCompany"})
                company_name = company_name_tag.get_text(strip=True) if company_name_tag else 'N/A'

                company_logo_container = job_card.find('div', attrs={"data-automation": "company-logo-container"})
                company_logo_tag = company_logo_container.find('img') if company_logo_container else None
                company_logo = company_logo_tag['src'] if company_logo_tag and company_logo_tag.has_attr('src') else 'N/A'

                salary_tag = job_card.find('span', attrs={"data-automation": "jobSalary"})
                salary = salary_tag.get_text(strip=True).replace("\xa0", "").replace("\u2013", "-") if salary_tag else 'N/A'

                location_tags = job_card.find_all('a', attrs={"data-automation": "jobLocation"})
                location = ', '.join([tag.get_text(strip=True) for tag in location_tags]) if location_tags else 'N/A'

                link_tag = job_card.find('a', href=True, attrs={"data-automation": "jobTitle"})
                link = f"https://{url.split('/')[2]}{link_tag['href']}" if link_tag else 'N/A'

                results.append({
                    'title': title,
                    'company_name': company_name,
                    'company_logo': company_logo,
                    'salary': salary,
                    'location': location,
                    'link': link,
                })

            pagination = soup.find('ul', class_='_32fem00 _32fem03 _1nh354w5c _1nh354wh0')
            current_page = page
            last_page = 1 
            has_next = False
            if pagination:
                page_tags = pagination.find_all('a', attrs={"data-automation": re.compile(r"page-\d+")})
                if page_tags:
                    last_page_numbers = [
                        int(tag.get_text(strip=True)) for tag in page_tags if tag.get_text(strip=True).isdigit()
                    ]
                    last_page = max(last_page_numbers, default=1)

                next_button = pagination.find('a', rel="nofollow next")
                has_next = next_button is not None

            return ResponseHelper.success_response('Success find job', {
                'total_jobs': total_jobs,
                'jobs': results,
                'pagination': {
                    'current_page': current_page,
                    'last_page': last_page,
                    'has_next': has_next
                }
            })

        except Exception as e:
            traceback.print_tb(e.__traceback__)
            return ResponseHelper.failure_response(f"Error: {str(e)}")
        
    def search_karir(self, work = "Programmer", work_option="", page = 1, cookies_file = 'config/karir.json'):
        work_options = {
            "": "",
            "onsite": "2",
            "hybird": "3",
            "remote": "1"
        }

        option_works_input = [w.strip().lower() for w in work_option.split(',') if w.strip()]
        option_works_param = ','.join([work_options[w] for w in option_works_input if work_options[w]])
        invalid_option_works = [w for w in option_works_input if w not in work_options]

        if invalid_option_works:
            return ResponseHelper.failure_response(f"Invalid option_work: {invalid_option_works}. valid options: {list(work_option)}")

        data = {
            "keyword": work,
            "locale": "id"
        }

        limit = 20
        offset = (page - 1) * limit

        data = {
            "keyword": work,
            "locale": "id",
            "workplace": option_works_param,
            "limit": limit,
            "offset": offset
        }

        scraper = CloudScraper.get_instance(cookies_file)
        response = scraper.post(self.api_karir_url, data = json.dumps(data)).json()
        results = []
        if response['data']['opportunities']:
            for jobs in response['data']['opportunities']:
                salary_lower = jobs['salary_lower']
                salary_upper = jobs['salary_upper']
                salary = f"Rp. {salary_lower:,}".replace(",", ".") + " - " + f"Rp. {salary_upper:,}".replace(",", ".") if salary_lower and salary_upper else "N/A"
                result = {
                    "title": jobs['job_position'],
                    "company_name": jobs['company_name'],
                    "company_logo": jobs['company_logo_url'],
                    "salary": salary,
                    "location": jobs['description'],
                    "link": f"https://karir.com/opportunities/{jobs['id']}",
                }
                results.append(result)
        
        total_jobs = response['data']['total_opportunities']
        last_page = math.ceil(total_jobs / limit)
        has_next = page < last_page

        return ResponseHelper.success_response('Success find job', {
            'total_jobs': total_jobs,
            'jobs': results,
            'pagination': {
                'current_page': page,
                'last_page': last_page,
                'has_next': has_next
            }
        })