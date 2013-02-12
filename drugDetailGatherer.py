import re, os, sys, csv
import urllib2, cookielib, mechanize
from time import time

fda_labeler_url = 'http://www.accessdata.fda.gov/scripts/cder/ndc-old/queryndclbl.cfm'
fda_appNum_url = 'http://www.accessdata.fda.gov/scripts/cder/drugsatfda/index.cfm?fuseaction=Search.Addlsearch_drug_name'
fda_root1_url = 'http://www.accessdata.fda.gov/scripts/cder/drugsatfda/'
fda_root2_url = 'http://www.accessdata.fda.gov/scripts/cder/ndc/'
fda_generics_url = 'http://www.accessdata.fda.gov/scripts/cder/drugsatfda/index.cfm?fuseaction=Search.Generics'
fda_labelerName_url = 'http://www.accessdata.fda.gov/scripts/cder/ndc/labelername.cfm'

br = mechanize.Browser()
cj = cookielib.LWPCookieJar()
br.set_cookiejar(cj)
br.set_handle_equiv(True)
br.set_handle_gzip(True)
br.set_handle_redirect(True)
br.set_handle_robots(False)   # no robots
br.set_handle_referer(True)
br.set_handle_refresh(mechanize._http.HTTPRefreshProcessor(), max_time=10)
br.addheaders = [('User-agent', 'Mozilla/6.0 (X11; U; i686; en-US; rv:1.9.0.1) Gecko/2008071615 OS X 10.2 Firefox/3.0.1')]

labelerBook = []
currentLabeler = 0

def get_drug_manifest(path):
# Returns a list of player names from CSV file
	reader=csv.reader(open(path,'Ub'),delimiter=',')
	drug_manifest=[]
	row_num = 0
	for row in reader:
		if row_num == 0:
			row_num += 1
			f = open('new ' + path,"wb")
			writer = csv.writer(f)
			writer.writerow(row)
			f.close()
		else:
			if row_num == 1:
				drug_manifest.append([row[2],[[row[3],row_num,1]],1])
			else: 
				if drug_manifest[-1][0] != row[2]: 
					drug_manifest[-1].append(row_num - 1)
					drug_manifest.append([row[2],[[row[3],row_num,1]],row_num])
				else:
					if drug_manifest[-1][1][-1][0] != row[3]:
						drug_manifest[-1][1].append([row[3],row_num,1])
					else:
						drug_manifest[-1][1][-1][2] += 1
			row_num += 1
	drug_manifest[-1].append(row_num - 1)
	for i in drug_manifest:
		i[1].sort(key=lambda x:int(x[0]))
	return drug_manifest
	
def get_drug_details(appNum):
	start = time()
	br.open(fda_appNum_url)
	br.select_form(name = 'searchoptionB')
	br.form['ApplNo'] = appNum
	response = br.submit(name = 'Search_Button')
	
	if response.geturl().count('Search.DrugDetails')==0:
		try:
			for l in response.readlines():
				if l.count('class="product_table')>0 and l.count('href'):
					keyword = re.findall(r'"(.*?)"',l)[3]
					response = br.open(fda_root1_url + keyword)
					break
		except UnicodeDecodeError:
			print 'Ignoring UnicodeDecodeError'
	
	if response.geturl().count('Search.DrugDetails')==0:
		try:
			count = 0
			for l in response.readlines():
				if l.count(appNum)>0:
					keyword = re.findall(r'"(.*?)"',l)[0]
					response = br.open(fda_root1_url + keyword)
					break
		except UnicodeDecodeError:
			print 'Ignoring UnicodeDecodeError'
	#print time() - start
	if response.geturl().count('Search.DrugDetails')>0:
		return response
	else:
		print 'No Drug Details After 2 Redirections'
		return '-1'
		
def get_labeler_name(labeler_code, currentLabeler):
	while (currentLabeler < len(labelerBook) and int(labelerBook[currentLabeler][0]) < int(labeler_code)):
		currentLabeler += 1
	if int(labelerBook[currentLabeler][0]) != int(labeler_code):
		return -1
	else:
		return labelerBook[currentLabeler][1]
		
def download_to_files(files_list):
	if len(files_list) == 0:					# for an element list in files list : 0 - csv file name. 1 - number, not relevent.
		return
	for file in files_list:
		drug_manifest = get_drug_manifest(file[0])
		reader=csv.reader(open(file[0],'U'),delimiter=',')
		f = open('new ' + file[0],"ab")
		writer = csv.writer(f)
		reader.next()
		for i in drug_manifest:
			product_appNum = []
			if int(file[0][:4]) < 2005:
				br.open(fda_labeler_url)
				br.select_form('FrontPage_Form1')
				labeler = str(i[0]).zfill(5)			# query for product code and corresonding application #
				print labeler
				br.form['lblcode'] = labeler
				response = br.submit()
				
				count = 0

				for l in response.readlines():
					try:
						if l.count('<td valign="TOP')>0 and l.count('face')==0:
							if count == 1 or count == 2:
								keyword = l[l.find('>')+1:]
								keyword = keyword[:keyword.find('<')]
								if count == 1:
									product_appNum.append([keyword])			# add new product code
								else:
									if keyword == 'BLA' or keyword.isdigit():		# if application # is digit or BLA, add it
										product_appNum[-1].append(keyword)			# else erase product code
									else:
										product_appNum.pop()
								count += 1
							else:
								count = (count + 1) % 6
					except UnicodeDecodeError:
						print 'Ignoring UnicodeDecodeError'
			else:
				labeler_name = get_labeler_name(i[0], currentLabeler)
				br.open(fda_labelerName_url)
				br.select_form(nr = 1)
				br.form['searchfield'] = labeler_name
				response = br.submit()			
				next_sections = []
				count = -1
				for l in response.readlines():
					if l.count('numberperpage=')>0 and l.count('<strong>')>0:
						keyword = re.findall(r'"(.*?)"',l)[0]
						next_sections.append(keyword)
						continue
					if l.count('scope="row"')>0:
						keyword = l[l.find('>')+1:]
						keyword = keyword[:keyword.find('<')]
						keyword = keyword.split('-')[1]			# we want the product code which is after the hyphen
						product_appNum.append([keyword])
						count = 0
					if count == 10:
						count = -1
						keyword = re.findall(r'"(.*?)"',l)[0]
						if keyword[:3] != 'NDA' and keyword[:4] != 'ANDA':
							product_appNum.pop()
							continue
						keyword = keyword[keyword.find('A')+1:]
						product_appNum[-1].append(keyword)
					if count != -1:
						count += 1
				for url in next_sections:
					count = -1
					response = br.open(fda_root2_url + url)
					for l in response.readlines():
						if l.count('scope="row"')>0:
							keyword = l[l.find('>')+1:]
							keyword = keyword[:keyword.find('<')]
							keyword = keyword.split('-')[1]			# we want the product code which is after the hyphen
							product_appNum.append([keyword])
							count = 0
						if count == 10:
							count = -1
							keyword = re.findall(r'"(.*?)"',l)[0]
							if keyword[:3] != 'NDA' and keyword[:4] != 'ANDA':
								product_appNum.pop()
								continue
							keyword = keyword[keyword.find('A')+1:]
							product_appNum[-1].append(keyword)
						if count != -1:
							count += 1
			if len(product_appNum) != 0:
				product_appNum.sort(key = lambda x: x[0])			# sort by product code
				
				#print product_appNum

				loc_prodInd = 0
				rem_prodInd = 0
				sum_appNums = 0
				
				while loc_prodInd < len(i[1]) and rem_prodInd < len(product_appNum):
					if int(i[1][loc_prodInd][0]) < int(product_appNum[rem_prodInd][0]):
						i[1][loc_prodInd].append('1234567')
						i[1][loc_prodInd].append('notFound')				# match product codes and append app # to local list if applicable
						loc_prodInd += 1									# if not applicable, append string '1234567' for sorting
						continue
					if int(i[1][loc_prodInd][0]) > int(product_appNum[rem_prodInd][0]):
						rem_prodInd += 1
						continue
					if product_appNum[rem_prodInd][1] == 'BLA':
										i[1][loc_prodInd].append('1234567')	# if application number is BLA
										i[1][loc_prodInd].append('BLA')		# append string '1234567' for sorting
					sum_appNums += 1										# also append 'BLA' for identification
					i[1][loc_prodInd].append(product_appNum[rem_prodInd][1])
					loc_prodInd += 1
					rem_prodInd += 1
			
				while loc_prodInd < len(i[1]):
					i[1][loc_prodInd].append('1234567')		# if remote list is first depleted
					i[1][loc_prodInd].append('notFound')	# continue to label all the rest as 'notFound'
					loc_prodInd += 1

				i[1].sort(key = lambda x: int(x[3]))		# sort by application number

				print 'sorting finished:'
				for obj in i[1]:					# when sorting finished, print product table
					print obj

				loc_prodInd = 0

				while i[1][loc_prodInd][3] != '1234567':
					if int((loc_prodInd * 10.0)/sum_appNums) != int(((loc_prodInd-1)*10)/sum_appNums):		#print progress indicator
						print int((loc_prodInd * 10.0)/sum_appNums)
					if loc_prodInd != 0 and i[1][loc_prodInd-1][3] == i[1][loc_prodInd][3]:
						i[1][loc_prodInd].extend(i[1][loc_prodInd-1][4:len(i[1][loc_prodInd-1])])		# if app # has been queried
						#print i[1][loc_prodInd]														# use query result
						loc_prodInd += 1
						continue	
					print 'looking for initial appNum:'	+ i[1][loc_prodInd][3]			# look application number for drugDetails page
					response2 = get_drug_details(i[1][loc_prodInd][3])
					if response2 == '-1':												# if cannot find drugDetails
						i[1][loc_prodInd][3] = '1234567'								# change this entry's label to 'notFound'
						i[1][loc_prodInd].append('notFound')
						loc_prodInd += 1
						continue
					next_is_needed = -1
					for l in response2.readlines():
						try:
							if next_is_needed == -1:
								if l.count('class="details_table')>0:
									if l.count('Application No')>0:						# if spoted details table, set indicator ready
										next_is_needed = 0
									elif l.count('Active Ingredient')>0:
										next_is_needed = 1
							else:
								right = l[l.find('>')+1:]
								right = right[right.find('>')+1:]
								keyword = right[:right.find('<')]				# indicator tells what type of info is available
								if next_is_needed == 0:							# if NDA, product is brand drug, else generic
									if keyword[1] == 'N':
										i[1][loc_prodInd].append('Brand')
									else:
										i[1][loc_prodInd].append('Generic')
										break
								else:
									i[1][loc_prodInd].append(keyword)			# app # comes before ingredient name
							
								next_is_needed = -1
							if l.count('There are no Ther')>0:
								#print 'no Ther'
								i[1][loc_prodInd].append('NoTE')			# if no therapeutic equivalence string is found
								i[1][loc_prodInd][5] = ''					# set NoTE and clear the generic name field
								break
							if l.count('>Ther')>0 or l.count('Other OTC D')>0:		# if therapeutic equivalent or other OTC drugs are avilable
								ther_eq_opener = br.open(fda_generics_url)			# click in to find the 
								smallest_appNum = '9999999'
								count = 0
								countApp = 0
								flag = False
								for line in ther_eq_opener.readlines():
									if flag == False and line.count('table_header')>0:
										if line.count('Application<br>Number')==0:		# record column position of app #
											countApp += 1								
										else:
											flag = True
									if line.count('valign="top">')>0:
										if count == countApp:
											count += 1
											keyword = line[line.find('>')+1:]
											keyword = keyword[:keyword.find('<')]
											if int(keyword) == int(i[1][loc_prodInd][3]):	# if found app # is the same as brand drug, skip to next
												continue
											if int(keyword)	< int(smallest_appNum):			# if found app # is smaller than last known smallest, update
												smallest_appNum = keyword
										elif count == countApp+1:				# if count hit column amount, reset count
											count = 0
										else:
											count += 1
								i[1][loc_prodInd].append('Yes')				# found the smallest element
								i[1][loc_prodInd].append(smallest_appNum)	# append smallest generic app #
								print 'looking for minimum appNum approval date...'
								small_response = get_drug_details(smallest_appNum)		# look up smallest generic app #
								next_is_date = -1
								if small_response == '-1':
									i[1][loc_prodInd].append('invalid Generic Application #')	# if smallest generic app # is invalid, say it in date field
									continue
								for small_l in small_response.readlines():
									if next_is_date == -1:
										if small_l.count('class="details_table')>0 and small_l.count('Approval Date')>0:
											next_is_date = 0
									else:
										keyword = small_l[small_l.find('>')+1:]
										keyword = keyword[keyword.find('>')+1:]
										keyword = keyword[:keyword.find('<')]
										i[1][loc_prodInd].append(keyword)
										#print 'approval date found'
										break
								break				# break for all information of this app # is gathered
								
						except UnicodeDecodeError:
							print "Ignoring UnicodeDecodeError"
					print i[1][loc_prodInd]
					loc_prodInd += 1
				
				i[1].sort(key = lambda x: x[1])		# sort all entries of same labeler code by place in input csv file
				for obj in i[1]:
					print obj
			
			
			
			loc_index = 0
			count = 0

			for iter in xrange(i[2], i[3] + 1):
				row = reader.next()
				
				packSize = row[4]
				periodCover = row[5]
				drugName = row[6]
				unit = row[15]
				presNum = row[16]
				total = row[17]			# these columns change ever 
				medicaid = row[18]
				nonMedicaid = row[19]
				
				if count == 0:
					stateCode = row[0]
					firms = row[1]
					labeler = row[2]
					productCode = row[3]
					genBrand = row[7]
					appNum = row[8]
					comment = row[9]
					genAvail = row[10]
					nameGen = row[11]
					dateAvail = row[12]
					priceIssue = row[13]
					genEarliestAppnum = row[14]
					if len(product_appNum) != 0:	
						if i[1][loc_index][4] == 'Brand':
							appNum = i[1][loc_index][3]
							genAvail = i[1][loc_index][6]
							nameGen = i[1][loc_index][5]
							if genAvail == 'Yes':
								dateAvail = i[1][loc_index][8]
								genEarliestAppnum = i[1][loc_index][7]
							genBrand = 'Brand'
						elif i[1][loc_index][4] == 'Generics':
							genBrand = 'Generics'
						elif i[1][loc_index][4] == 'BLA':
							comment = 'BLA'
					count += 1					
				else:
					count += 1
				current_row = [stateCode, firms, labeler, productCode, packSize, periodCover, drugName, genBrand, appNum, comment, genAvail, nameGen, dateAvail, priceIssue, genEarliestAppnum, unit, presNum, total, medicaid, nonMedicaid]
				if count == i[1][loc_index][2]:
					count = 0
					loc_index += 1	
				writer.writerow(current_row)
			del i
		f.close()
		del drug_manifest
		
def main():
	numFile = 0
	inFiles = []
	print 'Available files:'
	for i in os.listdir('.'):
		if (i.count('.csv')>0 or i.count('.CSV')>0) and i[:3] != 'new' and i.count('labelerName.csv')==0:
			inFiles.append([i,numFile])
			print i + '       ' + str(numFile)
			numFile += 1
	feedback = raw_input('Please select files you don\'t need, enter files by number sequentially, separated by commas. If none write NONE: ')
	if feedback != 'NONE':
		feedback = feedback.split(',')
		availFile = 0
		delFile = 0
		while delFile < len(feedback):
			if inFiles[availFile][1] > int(feedback[delFile]) or int(feedback[delFile]) >= len(inFiles):
				print 'Incorrect Ommission Index.'
				exit()
			if inFiles[availFile][1] < int(feedback[delFile]):
				availFile += 1
				continue
			inFiles.pop(availFile)
			availFile += 1
			delFile += 1
	
	reader=csv.reader(open('labelerName.csv','U'),delimiter=',')
	rowNum = 0
	for row in reader:
		if rowNum ==0:
			rowNum += 1
		else:
			labelerBook.append([row[0], row[1]])
	
	download_to_files(inFiles)

main()