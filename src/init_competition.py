from models import Team

from namespaces_logic import create_namespace

def init_competition():
    # Create namespaces for existing teams
    teams = Team.query.all()
    for team in teams:
        create_namespace(team.id)



    
  
