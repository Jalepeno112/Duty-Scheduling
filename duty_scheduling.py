import pandas as pd
import re
import os
import numpy as np
import math
import itertools
import argparse


def run(filename, outfile, current=None):

    df = loadDataFrame(filename)
    num_users = len(df.columns) - 1

    # now with each of the day counts and preferences,
    # we can schedule for each day type seperately
    quarter_schedule = pd.DataFrame(columns=['CF1', 'CF2', 'CF1 Pref', 'CF2 Pref'], index=df.index.values)

    # if this is a continuation of an old schedule, then we want to add the old values
    if current:
        print("Loading current schedule")
        current_schedule = loadOldSchedule(current)
        quarter_schedule = pd.concat([current_schedule, quarter_schedule])
        current_schedule_counts = current_schedule.groupby("Type").count()

    # define the heirarchy in which days are scheduled
    # we do weekends, then wednesdays, then weekedays
    type_order = ['Weekend', 'Wednesday', 'Weekday']
    level_order = ['Most Preferred', 'Acceptable', 'Not Preferred', 'Not Available']

    # now we calculate how many of each day type there are
    # this is done only for the current schedule
    grouped = df.groupby("Type")
    counts = grouped.count()

    user_index = 0    #starting user index

    for day in type_order:
        print ("Scheduling {0}".format(day))
        group = grouped.get_group(day)

        # calculate what the equal share of this type of day is.
        # we also have to check if there was an old schedule, because that will make a difference in the totals
        # if the old schedule is present, use the number of each type of day (calculated earlier)
        # then calculate the equal share for the last schedule and add it to the calculation for this schedule
        # if there is no old schedule, then just add 0       
        current_equal_share = calculateEqualShare(current_schedule_counts, day, num_users, ceil=True) if current else 0
        equal_share = calculateEqualShare(counts, day, num_users, ceil=True) + current_equal_share
        equal_share = int(math.ceil(equal_share))
        print("OLD EQUAL_SHARE: {0}".format(current_equal_share))
        print("EQUAL_SHARE: {0}".format(equal_share))

        # we want to compute which days are the most challenging to schedule on
        # e.g. the ones with the least number of Most Preferred or Acceptable
        day_hierarchy = group.copy()
        del(day_hierarchy['Type'])
        for i in range(len(level_order)):
            day_hierarchy.replace(level_order[i], i, inplace=True)

        # sum the rows.
        # the days with a higher count are the harder to schedule
        # so we sort in descending order
        day_preferences = day_hierarchy.sum(axis=1).sort_values(ascending=False)

        print(day_preferences)

        # re-order the group by the day_preferences order
        group = group.ix[day_preferences.index]

        levels = ['Most Preferred', "Acceptable", "Not Preferred", "Not Available"]
        users = list(df.columns[:-1].values)
        
        schedule_complete = False
        
        date_index = 0
        schedule = pd.DataFrame(columns=['CF1', 'CF2'], index=group.index.values)

        # in the event that there is an old schedule, we need a way to account for it.
        # do this in the same way that we did earlier.
        # simulate the data structure by appending the new, empty dataframe onto the old one
        if current:
            current_grouped = current_schedule.groupby("Type")
            schedule = pd.concat([current_grouped.get_group(day)[['CF1', 'CF2']], schedule])
            print("Loaded old schedule values")
            print schedule

        del(group['Type'])

        increase_level = 0
        dead_runs = 0
        
        # we are going to loop through and schedule each day
        # on each day, we loop through each user and pick the first two users that are free for a given day
        # This means that we need to pick a start position in the user list and iterate through
        # if we make a full loop on a given day, then we increase the range of accepable levels
        # if we reach the max range of acceptable levels and still haven't scheduled anyone, then its a dead run and we move on

        for date in group.index:
            day_scheduled = False
            level_index = 1

            # hold on to the index where we started.  If we make it back to this index while scheduling a given day,
            # then we have checked all users and need to increase our level threshold and try again
            initial_user_index = user_index

            print ("Scheduling {0} starting at position {1}".format(date, initial_user_index))
            while not day_scheduled:
                # get the users that can take this day within the levels of acceptance
                msk = group.ix[date].isin(levels[0:level_index+1])
                usable = group.ix[date][msk]

                # if noone is within the acceptable levels, then we need to increase the level
                if usable.empty:
                    level_index = level_index + 1
                    print ('No acceptable users found.  Increasing level to {0}'.format(level_index))
                    print ("Users: {0}".format(group.columns.values))
                    if level_index >= len(levels):
                        print("Could not schedule anyone on this day: {0}".format(date))
                        break

                else:
                    # now go through the list of users based on our *user_index*
                    # if the current user is in the list, select them
                    # increment the *user_index* counter
                    user = users[user_index]
                    if user in usable.index:
                        # check to see if CF has met quota.
                        # if they have, then remove them from the list
                        if len(schedule[~schedule[schedule==user].isnull().all(axis=1)]) >= equal_share:
                            del(group[user])
                            print("Removing {0} from rotation.".format(user))
                            print("Users left: {0}".format(group.columns))

                        # make sure that we aren't putting anyone on too much
                        # by default, make sure that we aren't putting anyone on more than 3 times in 6 days
                        elif tooManyDaysCheck(quarter_schedule, date, user):
                            # check if they are the first or second person being assigned to this day.
                            # if they are the second person, remove the day from the group dataframe so we don't attempt to schedule anyone else
                            if pd.isnull(quarter_schedule.ix[date, 'CF1']):
                                quarter_schedule.ix[date, 'CF1'] = user
                                quarter_schedule.ix[date, 'CF1 Pref'] = group.ix[date,user]
                                schedule.ix[date, 'CF1'] = user
                                print "Scheduled CF1: {0} for {1}".format(user, date)
                            elif not quarter_schedule.ix[date, 'CF1'] == user and pd.isnull(quarter_schedule.ix[date,'CF2']):
                                quarter_schedule.ix[date,'CF2'] = user
                                quarter_schedule.ix[date, 'CF2 Pref'] = group.ix[date,user]
                                schedule.ix[date, 'CF2'] = user

                                group.drop(date, inplace=True)
                                print "Scheduled CF2: {0} for {1}".format(user, date)
                                print "Day is done: {0}".format(date)
                                day_scheduled = True

                           


                    user_index = user_index + 1
                    # if user_index is out of range, we need to wrap it back to the beginning
                    if user_index == len(users):
                        print("Reached end of user list at position {0}!  Wrapping around!".format(user_index))
                        user_index = 0
                        users = users[::-1]


                    # if the user_index once again equals the initial_user_index
                    # then we have checked all users with the current levels
                    # increase the range of acceptable levels and try again
                    if user_index == initial_user_index:
                        level_index = level_index + 1
                        print "Checked all users.  Increasing level: {0} our of {1}".format(level_index, len(levels))

                    # if the level_index has suprpased the range of acceptable levels,
                    # then we have tried all possible levels and we cannot find a good match
                    # at this point we need to move on
                    if level_index >= len(levels):
                        print "Checked all users under all levels.  Ending search for this day"
                        chosen_person = True
                        day_scheduled = True 
                        #initial_user_index = user_index
            print("Completed day\n---------------------------------------")

    quarter_schedule['Type'] = pd.concat([current_schedule['Type'], df['Type']])
    print(quarter_schedule)
    printTotals(quarter_schedule, users, type_order, levels)
    writeToSheet(quarter_schedule, users, type_order, outfile)

    return quarter_schedule

def loadDataFrame(csv_file):
    # read the responses
    df = pd.read_csv(csv_file)

    # preserve comments just in case
    # the dropna call will most likely drop this column since not everyone leaves comments
    comments = df['Additional comments']  if "Additional comments" in df.columns else None

    # drop any columns that have nothing but NA
    # these were likely leftover/ extra columns that have no meaning
    df = df.dropna(axis=1)

    # remove timestamp and user columns
    # these are predefined by Google sheets when making the form
    users = df['Username']
    names = df['Name'] if 'Name' in df.columns else None
    del(df['Username'])
    del(df['Timestamp'])

    if names is not None:
        del(df['Name'])

    # transpose the dataframe so that the dates are on the rows, 
    # and the CF names are the columns
    df = df.T
    df.columns = users

    # apply regex to pull the dates out of the columns
    pattern = re.compile("\[([A-Za-z]+) (\d+/\d+)")
    dates = [pattern.search(d).groups() for d in df.index.values]
    df.index = dates

    # tag the day as either a weekday, weekend or wednesday
    df['Type'] = [day_type(d[0]) for d in df.index.values]

    # once we've tagged by date, we can remove the day name from the index and just leave the numeric date
    df.index = [d[1] for d in df.index]
    return df
def calculateEqualShare(counts, day, num_users, ceil=True):
    """
    Calcualte the number of nights each CF needs to be on duty for a given type of day 

    :param counts:      pandas dataframe done by calling groupby_object.count()
    :param day:         the type of day (i.e. Weekday, Wednesday, Weekend)
    :param num_users:   the number of users that we have available
    """
    print "DAY: ", day, "\t",counts.ix[day].values[0], "\t", num_users
    equal_share = ((counts.ix[day].values[0] * 2) / float(num_users))
    print "DAY EQUAL: ", day, "\t", equal_share
    if ceil:
        equal_share = int(math.ceil(equal_share))
    return equal_share


def loadOldSchedule(old_schedule_file):
    df = pd.read_excel(old_schedule_file, sheetname="Day Schedule")
    cf1 = set(df['CF1'].unique())
    cf2 = set(df['CF2'].unique())

    users = list(cf1) + list(cf1 - cf2)
    replace = {u:u+"@scu.edu" if "@scu.edu" not in u else u for u in users}

    for u,r in replace.iteritems():
        df.replace(u, r, inplace=True)

    return df

def tooManyDaysCheck(quarter_schedule, date, user, tooMany = 3):
    day_index = list(quarter_schedule.index).index(date)
    min_index = trapValue(day_index - 3, 0, len(quarter_schedule)-1)
    max_index = trapValue(day_index + 3, 0, len(quarter_schedule)-1)

    # get all days within the range we are looking for 
    in_schedule = quarter_schedule.ix[quarter_schedule.index[min_index:max_index]]
    in_schedule = in_schedule[['CF1', 'CF2']]
    # get all days that this user is scheduled for within that subset
    print "Checking ", user
    print in_schedule
    msk = in_schedule[(in_schedule['CF1'] == user) | (in_schedule['CF2'] == user)]
    print msk
    num_days = (msk[msk == False]).shape[0]

    # check to see if adding one more day to this user's count will put them over the top
    if num_days + 1 >= tooMany:
        return False
    else:
        return True


def printTotals(df, users, days, levels):
    # count the number of times each unique value appears in each group
    # the count is going to be the same in every column because of the way count works
    # we can take the first column and then add it to 
    print("CF Stats: \n{0}\n---------------------------".format(_dayBreakdown(df, users, days)))

    # we also want to print the stats for the different levels (Most Preferred, Acceptable, Not Preferred, etc.)
    groupby_level = df.groupby(['CF1 Pref', 'CF2 Pref'])
    print("Team Stats: \n{0}\n---------------------------".format(groupby_level.count()['CF1']))
    level_permutations = [l for l in itertools.chain(itertools.product(levels[:-1], levels[:-1]))]


def trapValue(value, minimum, maximum):
    if minimum <= value and value <= maximum:
        return value
    elif value < minimum:
        return minimum
    else:
        return maximum


def _dayBreakdown(df, users, days):
    # count the number of times each unique value (user) appears in each group
    # the count is going to be the same in every column because of the way count works
    # we can take the first column and then add it to 
    groupby_type = df.groupby("Type")
    user_days ={
            u: {
                d: df[(df == u).any(axis=1)].groupby("Type").get_group(d).count()['CF1'] for d in days if u in groupby_type.get_group(d).values
            } for u in users
    }
    user_df = pd.DataFrame(user_days).fillna(0)

    user_df = user_df.T
    user_df['TotalDays'] = user_df.sum(1)
    user_df = user_df.T

    return user_df


def writeToSheet(df, users, days, filename):
    # we need a list of dicitonaries
    # each dictionary is a row in the spreadsheet.
    # the keys are the users, the values are the dates
    l = {u:list(df[(df==u).any(axis=1)].index.values) for u in users}

    d = pd.DataFrame(dict([ (k,pd.Series(v)) for k,v in l.iteritems() ]))

    writer = pd.ExcelWriter(filename)
    d.to_excel(writer,'CF Schedule')

    df.to_excel(writer, "Day Schedule")

    print "DAYS: ", days

    groupby_type = df.groupby("Type")
    user_df = _dayBreakdown(df, users, days)
    user_df.to_excel(writer, "Day Breakdown")
    writer.save()


def day_type(day):
    if day == 'Wednesday':
        return 'Wednesday'
    elif day == 'Friday' or day == 'Saturday':
        return 'Weekend'
    else:
        return 'Weekday'

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("file", help="Name of the file that has user responses")
    parser.add_argument("outfile", help="Name of the file to write the schedule to")
    parser.add_argument("--current", help="If this schedule is a continuation of an old schedule, include the old schedule file here", default=None)

    args = parser.parse_args()
    print(args)

    run(filename=args.file, outfile=args.outfile, current=args.current)

