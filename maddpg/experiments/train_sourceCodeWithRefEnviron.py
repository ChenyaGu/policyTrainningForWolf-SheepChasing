import os
import sys
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'
os.environ['KMP_DUPLICATE_LIB_OK']='True'
dirName = os.path.dirname(__file__)
sys.path.append(os.path.join(dirName, '..'))
sys.path.append(os.path.join(dirName, '..', '..'))
import logging
logging.getLogger('tensorflow').setLevel(logging.ERROR)
import argparse
import tensorflow.contrib.layers as layers
from gym import spaces
import pickle

from environment.chasingEnv.multiAgentEnv import *
from visualize.visualizeMultiAgent import *
import maddpg.maddpgAlgor.common.tf_util as U
from maddpg.maddpgAlgor.trainer.maddpg_try import MADDPGAgentTrainer


ddpg = False
policyPath = os.path.join(dirName, '..', 'policy1Wolf1SheepMADDPGWithTryTrain')

wolfSize = 0.075
sheepSize = 0.05
blockSize = 0.2

sheepMaxSpeed = 1.3
wolfMaxSpeed = 1.0
blockMaxSpeed = None

wolfColor = np.array([0.85, 0.35, 0.35])
sheepColor = np.array([0.35, 0.85, 0.35])
blockColor = np.array([0.25, 0.25, 0.25])


class GetTrainers:
    def __init__(self, numWolves, numAgents, obsShape, actionSpace):
        self.numWolves = numWolves
        self.numAgents = numAgents
        self.obsShape = obsShape
        self.actionSpace = actionSpace

    def __call__(self, trainer, model, arglist, useDDPG):
        trainers = []
        for i in range(self.numWolves):
            trainers.append(
                trainer("agent_%d" % i, model, self.obsShape, self.actionSpace, i, arglist, useDDPG))
        for i in range(self.numWolves, self.numAgents):
            trainers.append(
                trainer("agent_%d" % i, model, self.obsShape, self.actionSpace, i, arglist, useDDPG))

        return trainers


def mlp_model(input, num_outputs, scope, reuse=False, num_units=64, rnn_cell=None):
    # This model takes as input an observation and returns values of all actions
    with tf.variable_scope(scope, reuse=reuse):
        # out = input
        # out = layers.fully_connected(out, num_outputs=num_units, activation_fn=tf.nn.relu)
        # out = layers.fully_connected(out, num_outputs=num_units, activation_fn=tf.nn.relu)
        # out = layers.fully_connected(out, num_outputs=num_outputs, activation_fn=None)

        out = input
        out = layers.fully_connected(out, num_outputs=num_units, activation_fn=tf.nn.relu,
                                     weights_initializer=tf.initializers.glorot_uniform(seed=0))
        out = layers.fully_connected(out, num_outputs=num_units, activation_fn=tf.nn.relu,
                                     weights_initializer=tf.initializers.glorot_uniform(seed=0))
        out = layers.fully_connected(out, num_outputs=num_outputs, activation_fn=None,
                                     weights_initializer=tf.initializers.glorot_uniform(seed=0))

        return out


def parse_args():
    parser = argparse.ArgumentParser("Reinforcement Learning experiments for multiagent environments")
    # Environment
    parser.add_argument("--scenario", type=str, default="simple", help="name of the scenario script")
    parser.add_argument("--max-episode-len", type=int, default=25, help="maximum episode length")
    parser.add_argument("--num-episodes", type=int, default=60000, help="number of episodes")  # 60000
    parser.add_argument("--num-adversaries", type=int, default=3, help="number of adversaries")
    parser.add_argument("--good-policy", type=str, default="maddpg", help="policy for good agents")
    parser.add_argument("--adv-policy", type=str, default="maddpg", help="policy of adversaries")
    # Core training parameters
    parser.add_argument("--lr", type=float, default=1e-2, help="learning rate for Adam optimizer")
    parser.add_argument("--gamma", type=float, default=0.95, help="discount factor")
    parser.add_argument("--batch-size", type=int, default=1024, help="number of episodes to optimize at the same time")
    parser.add_argument("--num-units", type=int, default=64, help="number of units in the mlp")
    # Checkpointing
    parser.add_argument("--exp-name", type=str, default='exp', help="name of the experiment")
    parser.add_argument("--save-dir", type=str, default=policyPath,
                        help="directory in which training state and model should be saved")
    parser.add_argument("--save-rate", type=int, default=1000,
                        help="save model once every time this many episodes are completed")
    parser.add_argument("--load-dir", type=str, default="",
                        help="directory in which training state and model are loaded")
    # Evaluation
    parser.add_argument("--restore", action="store_true", default=False)
    parser.add_argument("--display", action="store_true", default=True)
    parser.add_argument("--benchmark", action="store_true", default=False)
    parser.add_argument("--benchmark-iters", type=int, default=100000, help="number of iterations run for benchmarking")
    parser.add_argument("--benchmark-dir", type=str, default=os.path.join(dirName, '..', 'benchmark_files'),
                        help="directory where benchmark data is saved")
    parser.add_argument("--plots-dir", type=str, default=os.path.join(dirName, '..', 'learning_curves'),
                        help="directory where plot data is saved")
    return parser.parse_args()


def main():
    wolvesID = [0]
    sheepsID = [1]
    blocksID = []

    numWolves = len(wolvesID)
    numSheeps = len(sheepsID)
    numBlocks = len(blocksID)

    numAgents = numWolves + numSheeps
    numEntities = numAgents + numBlocks

    entitiesSizeList = [wolfSize] * numWolves + [sheepSize] * numSheeps + [blockSize] * numBlocks
    entityMaxSpeedList = [wolfMaxSpeed] * numWolves + [sheepMaxSpeed] * numSheeps + [blockMaxSpeed] * numBlocks
    entitiesMovableList = [True] * numAgents + [False] * numBlocks
    massList = [1.0] * numEntities

    isCollision = IsCollision(getPosFromAgentState)
    rewardWolf = RewardWolf(wolvesID, sheepsID, entitiesSizeList, isCollision)
    punishForOutOfBound = PunishForOutOfBound()
    rewardSheep = RewardSheep(wolvesID, sheepsID, entitiesSizeList, getPosFromAgentState, isCollision,
                              punishForOutOfBound)

    rewardFunc = lambda state, action, nextState: \
        list(rewardWolf(state, action, nextState)) + list(rewardSheep(state, action, nextState))

    reset = ResetMultiAgentChasing(numAgents, numBlocks)
    observeOneAgent = lambda agentID: Observe(agentID, wolvesID, sheepsID, blocksID, getPosFromAgentState,
                                              getVelFromAgentState)
    observe = lambda state: [observeOneAgent(agentID)(state) for agentID in range(numAgents)]

    reshapeAction = ReshapeAction()
    getCollisionForce = GetCollisionForce()
    applyActionForce = ApplyActionForce(wolvesID, sheepsID, entitiesMovableList)
    applyEnvironForce = ApplyEnvironForce(numEntities, entitiesMovableList, entitiesSizeList,
                                          getCollisionForce, getPosFromAgentState)
    integrateState = IntegrateState(numEntities, entitiesMovableList, massList,
                                    entityMaxSpeedList, getVelFromAgentState, getPosFromAgentState)
    transit = TransitMultiAgentChasing(numEntities, reshapeAction, applyActionForce, applyEnvironForce, integrateState)

    isTerminal = lambda state: [False]* numAgents

    initObsForParams = observe(reset())
    obsShape = [initObsForParams[obsID].shape for obsID in range(len(initObsForParams))]

    worldDim = 2
    actionSpace = [spaces.Discrete(worldDim * 2 + 1) for agentID in range(numAgents)]

    getTrainers = GetTrainers(numWolves, numAgents, obsShape, actionSpace)
    trainer = MADDPGAgentTrainer
    model = mlp_model
    arglist = parse_args()
    trainers = getTrainers(trainer, model, arglist, useDDPG=ddpg)

    with U.single_threaded_session():
        U.initialize()

        episode_rewards = [0.0]  # sum of rewards for all agents
        agent_rewards = [[0.0] for _ in range(numAgents)]  # individual agent reward
        final_ep_rewards = []  # sum of rewards for training curve
        final_ep_ag_rewards = []  # agent rewards for training curve
        saver = tf.train.Saver()
        episode_step = 0
        train_step = 0
        t_start = time.time()

        state = reset()

        print('Starting iterations...')
        while True:
            obs_n = observe(state)
            # print('state', state[0], state[1])
            # action_n = [trainers[0].action(obs_n[0]), [0, 0, 0, 0, 0]]
            action_n = [agent.action(obs) for agent, obs in zip(trainers,obs_n)]

            nextState = transit(state, action_n)
            new_obs_n = observe(nextState)
            rew_n = rewardFunc(state, action_n, nextState)
            # print('reward ', rew_n)
            # print('state', nextState[0], nextState[1])
            # print('--')
            done_n = isTerminal(state)

            episode_step += 1
            done = all(done_n)
            terminal = (episode_step >= arglist.max_episode_len)

            for i, agent in enumerate(trainers):
                agent.experience(obs_n[i], action_n[i], rew_n[i], new_obs_n[i], done_n[i], terminal)

            state = nextState

            for i, rew in enumerate(rew_n):
                episode_rewards[-1] += rew
                agent_rewards[i][-1] += rew

            if done or terminal:

                state = reset()
                episode_step = 0
                episode_rewards.append(0)
                for a in agent_rewards:
                    a.append(0)

            # increment global step counter
            train_step += 1

            # update all trainers, if not in display or benchmark mode
            loss = None
            for agent in trainers:
                agent.preupdate()
            for agent in trainers:
                loss = agent.update(trainers, train_step)

            # save model, display training output
            if terminal and (len(episode_rewards) % arglist.save_rate == 0):
                # print('eps rewards', episode_rewards)

                U.save_state(arglist.save_dir, saver=saver)
                print("steps: {}, episodes: {}, mean episode reward: {}, agent episode reward: {}, time: {}".format(
                    train_step, len(episode_rewards), np.mean(episode_rewards[-arglist.save_rate:]),
                    [np.mean(rew[-arglist.save_rate:]) for rew in agent_rewards], round(time.time()-t_start, 3)))

                t_start = time.time()
                # Keep track of final episode reward
                final_ep_rewards.append(np.mean(episode_rewards[-arglist.save_rate:]))
                for rew in agent_rewards:
                    final_ep_ag_rewards.append(np.mean(rew[-arglist.save_rate:]))


            # saves final episode reward for plotting training curve later
            if len(episode_rewards) > arglist.num_episodes:
                rew_file_name = arglist.plots_dir + arglist.exp_name + '_rewards.pkl'
                with open(rew_file_name, 'wb') as fp:
                    pickle.dump(final_ep_rewards, fp)
                agrew_file_name = arglist.plots_dir + arglist.exp_name + '_agrewards.pkl'
                with open(agrew_file_name, 'wb') as fp:
                    pickle.dump(final_ep_ag_rewards, fp)
                print('...Finished total of {} episodes.'.format(len(episode_rewards)))
                break



if __name__ == '__main__':
    main()
