
class RewardWolfIndividual:
    def __init__(self, wolvesID, sheepsID, entitiesSizeList, isCollision, collisionReward=10):
        self.wolvesID = wolvesID
        self.sheepsID = sheepsID
        self.entitiesSizeList = entitiesSizeList
        self.isCollision = isCollision
        self.collisionReward = collisionReward

    def __call__(self, state, action, nextState):
        reward = []

        for wolfID in self.wolvesID:
            currentWolfReward = 0
            wolfSize = self.entitiesSizeList[wolfID]
            wolfNextState = nextState[wolfID]
            for sheepID in self.sheepsID:
                sheepSize = self.entitiesSizeList[sheepID]
                sheepNextState = nextState[sheepID]

                if self.isCollision(wolfNextState, sheepNextState, wolfSize, sheepSize):
                    currentWolfReward += self.collisionReward

            reward.append(currentWolfReward)
        return reward


class RewardWolfIndividualWithBiteAndKill:
    def __init__(self, wolvesID, sheepsID, entitiesSizeList, isCollision, getCaughtHistoryFromAgentState, sheepLife=3,
                 biteReward=1, killReward=10):
        self.wolvesID = wolvesID
        self.sheepsID = sheepsID
        self.entitiesSizeList = entitiesSizeList
        self.isCollision = isCollision
        self.getEntityCaughtHistory = lambda state, entityID: getCaughtHistoryFromAgentState(state[entityID])
        self.sheepLife = sheepLife
        self.biteReward = biteReward
        self.killReward = killReward

    def __call__(self, state, action, nextState):
        reward = []
        for wolfID in self.wolvesID:
            currentWolfReward = 0
            wolfSize = self.entitiesSizeList[wolfID]
            wolfNextState = nextState[wolfID]
            for sheepID in self.sheepsID:
                sheepSize = self.entitiesSizeList[sheepID]
                sheepNextState = nextState[sheepID]
                if self.isCollision(wolfNextState, sheepNextState, wolfSize, sheepSize):
                    currentWolfReward += self.biteReward
                sheepCaughtHistory = self.getEntityCaughtHistory(state, sheepID)
                if sheepCaughtHistory == self.sheepLife:
                    currentWolfReward += self.killReward
            reward.append(currentWolfReward)
        return reward
